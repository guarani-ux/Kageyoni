"""One JSON command surface and interactive menu for daily operation."""
import argparse
import json
import inspect
from .engine import Engine, require
from .application import Application

# Deliberate allowlist: no arbitrary attribute/method execution from command packets.
SERVICES = {
    'operations': {'status','settings','export_bundle','import_bundle','migrate_copy','propose_policy','trial_policy','activate_policy','rollback_policy'},
    'genesis': {'introduce','read'},
    'encounters': {'define','start','inspect','act'},
    'workspaces': {'open','read','list'},
    'transitions': {'enter','read','return_to_world','recover'},
    'documents': {'ingest','acquire_file','world_source','source','inquire','decompose','checked_candidates','draft','read'},
    'transfers': {'propose','read','run_trial','record_trial'},
    'artifacts': {'manifest','verify','recover'},
    'network': {'run','read','list','compare','compose','read_composition','record_coordination_lesson','coordination_lessons'},
    'repository': {'rebind','prepare','check','trial_artifact','promote','read','reconcile'},
    'pipelines': {'rebind','create','run','read','resume_manual','reconcile'},
    'nodes': {'list','read','bind'},
    'methods': {'list','read','create','revise','assign'},
    'learning': {'list','read','list_outcomes','read_outcome','record_outcome','propose','revise','review'},
    'contributions': {'list','read','run'},
    'simulation': {'capabilities','frames','graph','types','aspects','register_aspect','compile','resolve','compile_scene','resolve_scene','prepare_event','commit_event'},
    'knowledge': {'ingest','read','list','route','read_route','advance','to_aspect'},
}

def dispatch(engine, data):
    require(type(data) is dict,'command packet must be an object')
    require(set(data)<={'service','action','arguments'},'unknown command packet fields')
    service=data.get('service','operations'); action=data.get('action','status'); arguments=data.get('arguments',{})
    require(service in SERVICES and action in SERVICES[service],'unsupported service/action')
    require(type(arguments) is dict,'arguments must be an object')
    return getattr(getattr(Application(engine),service),action)(**arguments)

def describe(engine, service, action):
    require(service in SERVICES and action in SERVICES[service],'unsupported service/action')
    function=getattr(getattr(Application(engine),service),action)
    fields=[]
    for name,parameter in inspect.signature(function).parameters.items():
        if name=='viewer':continue
        required=parameter.default is inspect.Parameter.empty
        fields.append({'name':name,'required':required,**({} if required else {'default':parameter.default})})
    return {'service':service,'action':action,'fields':fields,'description':inspect.getdoc(function) or 'See docs/V4-CONTRACT.md through docs/V8-CONTRACT.md and examples/.','template':{'service':service,'action':action,'arguments':{x['name']:'<required>' for x in fields if x['required']}}}

def _choose(label, values):
    for index,value in enumerate(values,1):print(str(index)+'. '+value)
    raw=input(label+': ').strip()
    require(raw.isdigit() and 1<=int(raw)<=len(values),'invalid selection')
    return values[int(raw)-1]

def menu(engine):
    while True:
        print('\nDaily operation: 1 Status  2 Guided service action  3 Command JSON file  0 Back')
        choice=input('Action: ').strip()
        if choice=='0':return
        try:
            if choice=='1':packet={'action':'status'}
            elif choice=='3':
                with open(input('Command JSON file: ').strip(),encoding='utf-8') as handle:packet=json.load(handle)
            else:
                require(choice=='2','unknown menu choice')
                service=_choose('Service',list(SERVICES))
                actions=[x for x in sorted(SERVICES[service]) if hasattr(getattr(Application(engine),service),x)]
                action=_choose('Action',actions); contract=describe(engine,service,action)
                print(json.dumps(contract,indent=2,ensure_ascii=False)); arguments={}
                for field in contract['fields']:
                    label=field['name']+(' (required)' if field['required'] else ' [default '+json.dumps(field['default'])+']')
                    raw=input(label+': ').strip()
                    if not raw and not field['required']:continue
                    require(bool(raw),'required field omitted')
                    try:arguments[field['name']]=json.loads(raw)
                    except json.JSONDecodeError:arguments[field['name']]=raw
                packet={'service':service,'action':action,'arguments':arguments}
            print(json.dumps(dispatch(engine,packet),indent=2,ensure_ascii=False))
        except (ValueError,TypeError,OSError,KeyError,AttributeError) as exc:print('Action unresolved:',exc)

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',required=True); parser.add_argument('--input'); parser.add_argument('--initialize',action='store_true')
    args=parser.parse_args(argv); engine=Engine(args.db)
    try:
        if args.initialize:
            from .persistence.migrations import install_all
            install_all(engine)
        if args.input:
            with open(args.input,encoding='utf-8') as handle: data=json.load(handle)
            print(json.dumps(dispatch(engine,data),indent=2))
        else: menu(engine)
    finally: engine.close()

if __name__=='__main__':main()
