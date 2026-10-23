"""Fixed optional trusted-host bridge. No wire operation or Native service yet.

This module is not a bearer-token interface. Native code calls this fixed
authorization function; callers cannot substitute a callback. Only the trusted
launcher may supply the actual application/context. Hostile in-process Python
and direct connection manipulation are outside this trust model.
"""
def _authorize_current(app, context, request, unit):
    from .application import SamsaraApplication, CallerContext
    from .protocol import Fault
    from kageyoni.persistence.unit_of_work import _lexical_generation
    from kageyoni.workspaces.source_authority_operations import canonical
    from kageyoni.workspaces.source_authority_installation import strict_json

    def deny():
        raise Fault('UNAVAILABLE')

    if type(app) is not SamsaraApplication or type(context) is not CallerContext:
        deny()
    if app.engine.db is not app.db or unit.db is not app.db:
        deny()
    _lexical_generation(app.db, unit)
    # Exact primitive JSON and current fields precede any source diagnostics.
    canonical(request)
    if type(request) is not dict or type(request.get('operation')) is not dict:
        deny()
    name = request['operation'].get('name')
    if name not in ('source.capture', 'source.withdraw') or type(name) is not str:
        deny()
    if request.get('workspace_id') != app.workspace_id or request.get('branch') != app.branch or context.workspace_id != app.workspace_id:
        deny()
    if context.role != 'operator' or type(context.authority_epoch) is not int or context.authority_epoch < 1:
        deny()
    if not all(type(value) is str and value for value in (context.binding_id, context.principal_id, context.workspace_id)):
        deny()
    if type(request.get('request_id')) is not str or not request['request_id'] or type(request.get('expected_revision')) is not int:
        deny()
    row = SamsaraApplication.authorize(app, context)
    grants = strict_json(row['grants_json'])
    if type(grants) is not list or not all(type(value) is str for value in grants) or len(grants) != len(set(grants)) or name not in grants:
        deny()
    # authorize rereads active/epoch/principal/workspace/role/actor/activity.
    # Return only fixed host identity, never participant-provided authority.
    return (context.binding_id, context.principal_id, context.workspace_id,
            context.role, context.character_id, context.authority_epoch,
            context.activity_id, app.branch, name)


def _capture_capacity(app, context, request, unit):
    from .application import SamsaraApplication
    from .protocol import Fault
    _authorize_current(app,context,request,unit)
    if request['operation']['name'] != 'source.capture':raise Fault('UNAVAILABLE')
    # Same actual policy as app.put, before this distinct Native insertion.
    SamsaraApplication._artifact_capacity(app,request['operation']['text'])
