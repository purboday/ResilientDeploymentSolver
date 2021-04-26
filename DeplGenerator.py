from Cheetah.Template import Template
import json
class DeplGenerator():
    def __init__(self):
        self.templateDef = '''
        app $appName {
            #for $host, $actor in $deplMap 
            #if len($modelFile['actors'][actor]['formals']) > 0
            on ($host) ${actor}(#echo ', '.join($argsList[$actor]) #) ;
            #else
            on ($host) $actor;
            #end if
            #end for
            }
        '''
        
        #if then (  #echo ','.join([param+'=' for param in modelFile['actors'][actor]['formals']]) # ) else # ;
        
    def gen_deplModel(self, appName, deplMap):
        with open(appName+'.json') as f:
            modelFile = json.load(f)
        argsList = {}
        for actor in modelFile['actors']:
            argsList[actor] = [param['name']+'=' for param in modelFile['actors'][actor]['formals']]
        t = Template(self.templateDef, searchList = [{'appName' : appName, 'deplMap' : deplMap, 'modelFile' : modelFile, 'argsList' : argsList}])
        with open(appName+'auto.depl', 'w') as file:
            file.write(t.respond())

if __name__ == '__main__':
    gen = DeplGenerator()
    t = gen.gen_deplModel(appName, deplMap)
