from z3 import *
from ModelParser import ModelParser
import argparse
from configparser import ConfigParser
import time
from DeplGenerator import DeplGenerator   
        

# A = ['A1','A2','A3']
# D = [2,2,2]
# C = [['A1','A2']]
# S = [[['A1','A2'], ['A3']]]
# H = {}

# num_nodes = 3

HOSTCONF = '/usr/local/riaps/etc/riaps-hosts.conf'
HWSPEC = '/home/riaps/workspace/ResilientDeploymentSolver/hardware-spec.conf'
    
class OptimizationSolver():
    def __init__(self, A=[], D=[], C=[], S=[], H={}, R ={}):
        self.s = None
        self.X={}
        self.A = A
        self.D = D
        self.C = C
        self.S = S
        self.H = H
        self.R = R
        self.HW = {}
        self.nwSwitch = {}
        hwSpec = ConfigParser()
        hwSpec.read(HWSPEC)
        for hwObj in self.R['hw']:
            for host,hwType in hwObj.items():
                self.HW[hwType]=hwSpec[hwType]
        if 'nwSwitch' in self.R:
            self.nwSwitch[self.R['nwSwitch']] = {}
            self.nwSwitch[self.R['nwSwitch']]['ports']=hwSpec[self.R['nwSwitch']]['ports'].split(',')
            self.nwSwitch[self.R['nwSwitch']]['Mbps']=hwSpec[self.R['nwSwitch']]['speeds'].split(',')
            try: self.nwSwitch[self.R['nwSwitch']]['fullDuplex']=(hwSpec[self.R['nwSwitch']]['full_duplex']=='true')
            except KeyError:  self.nwSwitch[self.R['nwSwitch']]['fullDuplex'] = False
            print(str(self.nwSwitch))
        
    def absolute(self,x):
        return If(x >= 0,x,-x)
    
    def check_max(self,x):
        a = 0
        expr = None
        for b in x:
            if expr is None:
                expr = If(b >= a,b,a)
            else:
                expr = If(b >= expr,b,expr)
        return expr 
    
    def get_pairwiseDiff(self,input_mat, rows, cols):
        output = []
        for i in range(rows):
            row_sum1 = 0
            row_sum2 = 0
            for j in range(cols):
                row_sum1 += input_mat[i+1,j+1]
                row_sum2 += input_mat[(i+1)%rows + 1,j+1]
            output.append(self.absolute(row_sum1 - row_sum2))
        return output
    
    def check_row_assignment(self, rowNum, colNum, hostName):
        if hostName.startswith("Placeholder"):
            penalty = 0.5
            print(hostName)
        else:
            penalty = 0
        expr = If(Sum([self.X[rowNum+1,j+1] for j in range(colNum)]) > 0, 1+penalty , 0)
        return expr
    
    def calc_cpu_time(self, cpuObj, objType):
        if objType == 'actor':
            cpuTime = float(cpuObj['use'])/100 * float(cpuObj['interval'])
        elif objType == 'hw':
            cpuTime = float(cpuObj['cores'])*float(cpuObj['max_cpu'])*1000
        return cpuTime
    
    def calc_memory(self, memObj, objType):
        if objType == 'actor':
            memKB = float(memObj['use'])
        elif objType == 'hw':
            memKB = float(memObj['mem'])*float(memObj['max_mem'])*1024
        return memKB
    
    def calc_disk_space(self, spcObj, objType):
        if objType == 'actor':
            spcKB = float(spcObj['use'])
        elif objType == 'hw':
            spcKB = float(spcObj['spc'])*float(spcObj['max_spc'])*1024
        return spcKB
    def calc_network_bw(self, netObj, objType):
        if objType == 'hw':
            bwKB = 0
            for i in range(len(netObj['ports'])):
                bwKB += int(netObj['ports'][i]) * float(netObj['Mbps'][i]) * 1024
                
            if netObj['fullDuplex']:
                bwKB = bwKB * 2
        return bwKB

        
    # Create a "matrix" (list of lists) of integer variables
    # Add range constraints
    
    def solve_constraints(self,hostList=[], minCost=False, maxRed=False):
        if minCost:
            if len(self.A) - len(hostList) > 0:
                aDiff = len(self.A) - len(hostList)
                for i in range(aDiff):
                    hostList.append("Placeholder_%d" % i)
            
        num_nodes = len(hostList)
        if maxRed:
            print("solving for maximum redundancy for %d nodes" % num_nodes)
            self.s = Optimize()
        elif minCost:
            self.s = Optimize()
            print("solving for minimum nodes required to deploy given specifications")
        else:
            print("solving deployment for %d nodes" % num_nodes)
            self.s = Solver()
        for i in range(num_nodes):
            for j in range(len(self.A)):
                self.X[i+1,j+1] =Int("x_%s_%s" % (i+1, j+1))
                self.s.add(self.X[i+1,j+1] >= 0)
                self.s.add(self.X[i+1,j+1] <= 1)
            for entry in self.C:
                self.s.assert_and_track(Implies(Or([self.X[i+1,self.A.index(actor)+1] == 1 for actor in entry]), And([self.X[i+1,self.A.index(actor)+1] == 1 for actor in entry])), 'colc_%s_%d' %(hostList[i],self.C.index(entry)))
            for entry in self.S:
                if len(entry) == 2:
                    self.s.assert_and_track(Implies(Or([self.X[i+1,self.A.index(actor)+1] == 1 for actor in entry[0]]), And([self.X[i+1,self.A.index(actor)+1] == 0 for actor in entry[1]])), 'sep_%s_%d' %(hostList[i],self.S.index(entry)))
                else:
                    self.s.assert_and_track(Sum([self.X[i+1,self.A.index(actor)+1] for actor in entry]) <= 1, 'sep_%s_%d' %(hostList[i],self.S.index(entry)))
            # at least one actor in each node
#             self.s.add(Sum([self.X[i+1,j+1] for j in range(len(self.A))]) >= 1)
                
        # Add duplicate constraints
               
        for j in range(len(self.A)):
            if maxRed:
                self.s.assert_and_track(Sum([self.X[i+1,j+1] for i in range(num_nodes)]) >= self.D[j], 'copies_%s' % self.A[j])
            else:
                self.s.assert_and_track(Sum([self.X[i+1,j+1] for i in range(num_nodes)]) == self.D[j], 'copies_%s' % self.A[j])
            
        # Add host-actor constraints
        for i in range(num_nodes):
            for entry in self.H:
                for host, actors in entry.items():
                    if i != hostList.index(host):
                        self.s.assert_and_track(And([self.X[i+1, self.A.index(actor)+1] == 0 for actor in actors]), 'host_actor_%s_%s' % (hostList[i],host))
        # Add resource constraints
        for hostObj in self.R['hw']:
            for host, hwType in hostObj.items():
                print("considering resource limits on [%s] as per specifications for [%s]" % (host, hwType))
                if host == 'all':
                    # cpu
                    self.s.assert_and_track(And([Sum([self.X[i+1,j+1]*(self.calc_cpu_time(self.R[self.A[j]]['cpu'],'actor')) - self.calc_cpu_time(self.HW[hwType],'hw')*self.R[self.A[j]]['cpu']['interval'] for j in range(len(self.A)) if (self.A[j] in self.R and 'cpu' in self.R[self.A[j]])]) < 0 for i in range(num_nodes)]), 'cpu_all')
                    # memory
                    self.s.assert_and_track(And([Sum([self.X[i+1,j+1]*self.calc_memory(self.R[self.A[j]]['mem'],'actor') for j in range(len(self.A)) if (self.A[j] in self.R and 'mem' in self.R[self.A[j]])]) < self.calc_memory(self.HW[hwType],'hw') for i in range(num_nodes)]), 'mem_all')
                    #disk space
                    self.s.assert_and_track(And([Sum([self.X[i+1,j+1]*self.calc_disk_space(self.R[self.A[j]]['spc'],'actor') for j in range(len(self.A)) if (self.A[j] in self.R and 'spc' in self.R[self.A[j]])]) < self.calc_disk_space(self.HW[hwType],'hw') for i in range(num_nodes)]), 'spc_all')
                    # network bW
                    self.s.assert_and_track(And([Sum([self.X[i+1,j+1]*float(self.R[self.A[j]]['net']['rate']) for j in range(len(self.A)) if (self.A[j] in self.R and 'net' in self.R[self.A[j]])]) + self.check_max([0]+[self.X[i+1,j+1]*(float(self.R[self.A[j]]['net']['ceil']) - float(self.R[self.A[j]]['net']['rate'])) for j in range(len(self.A)) if (self.A[j] in self.R and 'net' in self.R[self.A[j]])]) < float(self.R['nic']['net_rate']) for i in range(num_nodes)]), 'net_all')
                    break
                else:
                    # cpu
                    self.s.assert_and_track(Sum([self.X[hostList.index(host)+1,j+1]*(self.calc_cpu_time(self.R[self.A[j]]['cpu'],'actor')) - self.calc_cpu_time(self.HW[hostObj[host]],'hw')* self.R[self.A[j]]['cpu']['interval']for j in range(len(self.A)) if (self.A[j] in self.R and 'cpu' in self.R[self.A[j]])])< 0,'cpu_%s' % hostObj)
                    # memory
                    self.s.assert_and_track(Sum([self.X[hostList.index(host)+1,j+1]*self.calc_memory(self.R[self.A[j]]['mem'],'actor') for j in range(len(self.A)) if (self.A[j] in self.R and 'mem' in self.R[self.A[j]])])< self.calc_memory(self.HW[hostObj[host]],'hw'),'mem_%s' % hostObj)
                    # disk space
                    self.s.assert_and_track(Sum([self.X[hostList.index(host)+1,j+1]*self.calc_disk_space(self.R[self.A[j]]['spc'],'actor') for j in range(len(self.A)) if (self.A[j] in self.R and 'spc' in self.R[self.A[j]])])< self.calc_disk_space(self.HW[hostObj[host]],'hw'),'spc_%s' % hostObj)    
                    # network bW
                    self.s.assert_and_track(Sum([self.X[i+1,j+1]*float(self.R[self.A[j]]['net']['rate']) for j in range(len(self.A)) if (self.A[j] in self.R and 'net' in self.R[self.A[j]])]) + self.check_max([0]+[self.X[i+1,j+1]*float(self.R[self.A[j]['net']]['ceil']) for j in range(len(self.A)) if (self.A[j] in self.R and 'net' in self.R[self.A[j]])]) < float(self.R['nic']['net_rate']), 'net_%s' %hostObj)
        if maxRed:        
            self.s.maximize(Sum([self.X[i+1,j+1] for i in range(num_nodes) for j in range(len(self.A))]))
            self.s.minimize(Sum([self.X[i+1,j+1]- Sum([self.X[i+1,j+1]for i in range(num_nodes) for j in range(len(self.A))])/len(self.X)**2 for i in range(num_nodes) for j in range(len(self.A))]))
            
        if minCost:
            self.s.minimize(Sum([self.check_row_assignment(i,len(self.A),hostList[i]) for i in range(num_nodes)]))
            
        if 'nwSwitch' in self.R:
            totalBW = 0
            for j in range(len(self.A)):
                if self.A[j] in self.R and 'net' in self.R[self.A[j]]:
                    totalBW += float(self.R[self.A[j]]['net']['ceil'])
            print("maximum outbound traffic = %f Mbps" % (totalBW/1024))
            switchBW = self.calc_network_bw(self.nwSwitch[self.R['nwSwitch']], 'hw')
            print("maximum network switch bandwidth = %f Mbps" % (switchBW/1024))
            
            if 0.9 * switchBW < totalBW:
                print("Warning!!! network traffic might exceed switch capacity!!!")
         
        print(self.s.check())
        solution = {}
        if self.s.check() == sat:
            m = self.s.model()
            row_format = ("{:^"+str(len(max(self.A))+5)+"}") * (len(self.A))
            row_format = "{:^"+str(len(max(hostList))+3)+"}"+row_format
            print(row_format.format(*(["Hosts"]+self.A)))
            minNodes = 0
            for i in range(num_nodes):
                r=[hostList[i]]
                rowSum = 0
                for j in range(len(self.A)):
                    r.append(str(m.evaluate(self.X[i+1,j+1])))
                    solution[i,j] = m.evaluate(self.X[i+1,j+1]).as_string()
                    rowSum += int(solution[i,j])
                if (minCost and rowSum > 0) or not minCost:
                    minNodes += 1
                    print(row_format.format(*r))
            if minCost:
                print(" Minimum number of nodes required for deployment: %d" % minNodes)
        else:
            for spec in self.s.unsat_core():
                spec = str(spec)
                if spec.startswith('colc'):
                    idx = int(spec[-1])
                    host = spec[spec.index('_')+1:-2]
                    print("Cannot colocate actors %s on host %s. Check the dspec file." % (','.join(self.C[idx]), host))
                if spec.startswith('sep'):
                    idx = int(spec[-1])
                    host = spec[spec.index('_')+1:-2]
                    print("Cannot separate actors %s on host %s. Check the dspec file." % (','.join(self.S[idx]), host))
                if spec.startswith('copies'):
                    act = spec[spec.index('_')+1:]
                    print("Cannot assign specified copies for actor %s. Check the dspec file." % act)
                if spec.startswith('host_actor'):
                    host = spec[spec.index('_')+1:]
                    print("Cannot maintain host-actor dependency for host %s. Check the dspec file." % host)
                if spec.startswith('cpu'):
                    host = spec[spec.index('_')+1:]
                    print("Cannot maintain cpu limits for  %s. Check the model file for actor limits and the hardware-spec.conf file for hardware specifications." % host)
                if spec.startswith('mem'):
                    host = spec[spec.index('_')+1:]
                    print("Cannot maintain memory limits for  %s. Check the model file for actor limits and the hardware-spec.conf file for hardware specifications" % host)
                if spec.startswith('spc'):
                    host = spec[spec.index('_')+1:]
                    print("Cannot maintain space limits for  %s. Check the model file for actor limits and the hardware-spec.conf file for hardware specifications" % host)
        return solution

    def solve_redundant_rr(self, hostList, maxRed=1):
        print("round robin allocation with redundancy %d" % maxRed)
        X_rr = {}
        for i in range(len(hostList)):
            for j in range(len(self.A)):
                X_rr[i+1,j+1]= 0 
        # assign to each node and repeat
        
        while sum([X_rr[m+1,n+1] for m in range(len(hostList)) for n in range(len(self.A))]) < len(self.A)*maxRed:
            lastj = []
            for i in range(len(hostList)):
                for j in range(len(self.A)):
                    if j not in lastj and X_rr[i+1,j+1] != 1:
                        assigned = sum([X_rr[k+1,j+1] for k in range(len(hostList))])
                        if assigned < maxRed:
                            X_rr[i+1,j+1] = 1
                            lastj.append(j)
                            break
                        else:
                            X_rr[i+1,j+1] = 0
                            
        row_format = ("{:^"+str(len(max(self.A))+5)+"}") * (len(self.A))
        row_format = "{:^"+str(len(max(hostList))+3)+"}"+row_format
        print(row_format.format(*(["Hosts"]+self.A)))
        for i in range(len(hostList)):
            r=[hostList[i]]
            for j in range(len(self.A)):
                r.append(str(X_rr[i+1,j+1]))
            print(row_format.format(*r))
        return X_rr
        
    
            
def main():
    
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="model file")
    parser.add_argument("-H", "--hosts", default="", help="list of hostnames, comma separated")    # List of hostnames to used instead of system configured file
    parser.add_argument("-f", dest='hostsFile', help="absolute path to user defined host file")
    parser.add_argument("-d", "--depl", action="store_true", help="create a template deployment file")
    parser.add_argument("-mR","--maxRed", action="store_true", help = "determine the maximum copies of each actor")
    parser.add_argument("-miC","--minCost", action="store_true", help = "determine the minimum nodes to deploy the model")
    args = parser.parse_args()
    
    if args.hosts:
        hostList = args.hosts.split(',')
    else:
        if args.hostsFile:
            hostsConfig = args.hostsFile
        else:
            hostsConfig = HOSTCONF
        config = ConfigParser()
        config.read(hostsConfig)
        hostList = config['RIAPS']['hosts'].split(',')
    starttime = time.time()
    parsedModel = ModelParser(args.model)
    parsedModel.parse_model()
    solver = OptimizationSolver(parsedModel.A,parsedModel.D,parsedModel.C,parsedModel.S,parsedModel.H, parsedModel.R)
    soln = solver.solve_constraints(hostList, args.minCost, args.maxRed)
    #sol2 = solver.solve_redundant_rr(hostList, maxRed=3)
    deplMap = []
    for key, val in soln.items():
        for reps in range(int(val)):
            deplMap.append((hostList[key[0]],parsedModel.A[key[1]]))
    print('total time = %f s' % (time.time()-starttime))
    deplModel = DeplGenerator()
    deplModel.gen_deplModel(parsedModel.appName, deplMap)
        
if __name__ == '__main__':
    main()
