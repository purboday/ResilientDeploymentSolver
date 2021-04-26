import argparse
import os
import json
from riaps.lang.lang import compileModel, LangError
import sys
from textx.metamodel import metamodel_from_file
from textx.export import metamodel_export, model_export
from textx.exceptions import TextXSemanticError, TextXSyntaxError
import textx.model

        
class ModelParser():
    def __init__(self, modelFileName):
        self.A = []
        self.D = []
        self.C = []
        self.S = []
        self.H = {}
        self.modelFileName = modelFileName
        self.appName = None
        
    def parse_model(self):
        thisFolder = '/home/riaps/workspace/ResilientDeploymentSolver'
        compiledApp = compileModel(self.modelFileName)
        self.appName = list(compiledApp.keys())[0]
        with open(self.appName+'.json') as f:
            data = json.load(f)
#             get list of actors
            for actor, actorObj in data['actors'].items():
                self.A.append(actor)
#                 self.D.append(actorObj['copies'] if actorObj['copies'] > 0 else 1)
                compInstList = []
                for compInst, compObj in actorObj['instances'].items():
                    compInstList.append(compInst)
#                     self.G[compInst]=compObj['members']
                self.C.append(compInstList)
        deplSpec = self.modelFileName.split('.')[0]+'.dspec'
        deplSpecObj = {}
        try:
            deplSpecMeta = metamodel_from_file(os.path.join(thisFolder,'depl_spec.tx'))
            exampleSpec = deplSpecMeta.model_from_file(deplSpec)
            deplSpecObj['name'] = exampleSpec.name
            deplSpecObj['copies'] = {entry.actor.name : entry.copies for entry in exampleSpec.copies}
            deplSpecObj['colocate'] = []
            for entry in exampleSpec.colocation:
                deplSpecObj['colocate'].append([actor.name for actor in entry.actors])
            deplSpecObj['separate']=[]
            for entry in exampleSpec.separation:
                if len(entry.actorsl) > 0:
                    deplSpecObj['separate'].append({'actorl': [actor.name for actor in entry.actorsl], 'actorr': [actor.name for actor in entry.actorsr]})
                elif len(entry.actors) > 0:
                    deplSpecObj['separate'].append({'actors': [actor.name for actor in entry.actors]})
            deplSpecObj['hostdeployment'] = []
            for entry in exampleSpec.hostdeployment:
                deplSpecObj['hostdeployment'].append({entry.host.name: [actor.name for actor in entry.actors]})
            print(str(deplSpecObj))
        except IOError as e:
            errMsg = "I/O error({0}): {1}".format(e.errno, e.strerror)
            raise LangError(errMsg)
        except TextXSyntaxError as e:
            errMsg = "Syntax error: %s" % e.args
            raise LangError(errMsg)
        except TextXSemanticError as e:
            errMsg = "Semantic error: %s" % e.args
            raise LangError(errMsg)
        except Exception as e: 
            errMsg = "Unexpected error %s:%s" % (sys.exc_info()[0],e.args())
            raise LangError(errMsg)
        self.D=[deplSpecObj['copies'][actor] if actor in deplSpecObj['copies'] else 1 for actor in self.A]
        self.C = deplSpecObj['colocate']
        self.S = [[entry['actorl'], entry['actorr']] if 'actorl' in entry else entry['actors'] for entry in deplSpecObj['separate']]
        self.H = deplSpecObj['hostdeployment']
            
            
        
if __name__=='__main__':
    parsed = ModelParser()
    parsed.parse_model()