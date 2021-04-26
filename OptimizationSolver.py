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
    
class OptimizationSolver():
    def __init__(self, A=[], D=[], C=[], S=[], H={}):
        self.s = None
        self.X={}
        self.A = A
        self.D = D
        self.C = C
        self.S = S
        self.H = H
        
    def absolute(self,x):
        return If(x >= 0,x,-x)

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

        
    # Create a "matrix" (list of lists) of integer variables
    # Add range constraints
    
    def solve_constraints(self,hostList, maxRed=False):
        num_nodes = len(hostList)
        print("solving optimization problem for %d nodes" % num_nodes)
        if maxRed:
            print("solving for maximum redundancy")
            self.s = Optimize()
        else:
            self.s = Solver()
        for i in range(num_nodes):
            for j in range(len(self.A)):
                self.X[i+1,j+1] =Int("x_%s_%s" % (i+1, j+1))
                self.s.add(self.X[i+1,j+1] >= 0)
                self.s.add(self.X[i+1,j+1] <= 1)
            for entry in self.C:
                self.s.add(Implies(Or([self.X[i+1,self.A.index(actor)+1] == 1 for actor in entry]), And([self.X[i+1,self.A.index(actor)+1] == 1 for actor in entry])))
            for entry in self.S:
                if len(entry) == 2:
                    self.s.add(Implies(Or([self.X[i+1,self.A.index(actor)+1] == 1 for actor in entry[0]]), And([self.X[i+1,self.A.index(actor)+1] == 0 for actor in entry[1]])))
                else:
                    self.s.add(Sum([self.X[i+1,self.A.index(actor)+1] for actor in entry]) <= 1)
            # at least one actor in each node
#             self.s.add(Sum([self.X[i+1,j+1] for j in range(len(self.A))]) >= 1)
                
        # Add duplicate constraints
               
        for j in range(len(self.A)):
            if maxRed:
                self.s.add(Sum([self.X[i+1,j+1] for i in range(num_nodes)]) >= self.D[j])
            else: 
                self.s.add(Sum([self.X[i+1,j+1] for i in range(num_nodes)]) == self.D[j])
            
        # Add host-actor constraints
        for i in range(num_nodes):
            for entry in self.H:
                for host, actors in entry.items():
                    if i != hostList.index(host):
                        self.s.add(And([self.X[i+1, self.A.index(actor)+1] == 0 for actor in actors]))
        if maxRed:        
            self.s.maximize(Sum([self.X[i+1,j+1] for i in range(num_nodes) for j in range(len(self.A))]))
        
        print(self.s.check())
        solution = {}
        if self.s.check() == sat:
            m = self.s.model()
            row_format = ("{:^"+str(len(max(self.A))+5)+"}") * (len(self.A))
            row_format = "{:^"+str(len(max(hostList))+3)+"}"+row_format
            print(row_format.format(*(["Hosts"]+self.A)))
            for i in range(num_nodes):
                r=[hostList[i]]
                for j in range(len(self.A)):
                    r.append(str(m.evaluate(self.X[i+1,j+1])))
                    solution[i,j] = m.evaluate(self.X[i+1,j+1]).as_string()
                print(row_format.format(*r))
            return solution
    def solve_redundant_rr(self, hostList, maxRed=1):
                
    
            
def main():
    
    parser = argparse.ArgumentParser()
    parser.add_argument("model", help="model file")
    parser.add_argument("-H", "--hosts", default="", help="list of hostnames, comma separated")    # List of hostnames to used instead of system configured file
    parser.add_argument("-f", dest='hostsFile', help="absolute path to user defined host file")
    parser.add_argument("-d", "--depl", action="store_true", help="create a template deployment file")
    parser.add_argument("-mR","--maxRed", action="store_true", help = "determine the maximum copies of each actor")
    args = parser.parse_args()
    
    if args.hosts:
        hostList = args.hosts.split(',')
    else:
        if args.hostsFile:
            hostsConfig = args.hostsFile
        else:
            hostsConfig = '/usr/local/riaps/etc/riaps-hosts.conf'
        config = ConfigParser()
        config.read(hostsConfig)
        hostList = config['RIAPS']['hosts'].split(',')
    starttime = time.time()
    parsedModel = ModelParser(args.model)
    parsedModel.parse_model()
    solver = OptimizationSolver(parsedModel.A,parsedModel.D,parsedModel.C,parsedModel.S,parsedModel.H)
    soln = solver.solve_constraints(hostList, args.maxRed)
    deplMap = []
    for key, val in soln.items():
        for reps in range(int(val)):
            deplMap.append((hostList[key[0]],parsedModel.A[key[1]]))
    print('total time = %f s' % (time.time()-starttime))
    deplModel = DeplGenerator()
    deplModel.gen_deplModel(parsedModel.appName, deplMap)
        
if __name__ == '__main__':
    main()
