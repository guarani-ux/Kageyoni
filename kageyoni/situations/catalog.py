from .models import SituationTemplate, Workflow, WorkflowStage

TEMPLATES = (
    SituationTemplate("research","research",("question",),("sources","constraints"),recommended_workflows=("research.default",)),
    SituationTemplate("production_brief","production",("objective","audience","deliverables","constraints"),("distribution","stakeholders","references","metrics"),recommended_workflows=("production_brief.default",)),
    SituationTemplate("campaign","communications",("objective","audience"),("channels","positioning","metrics","stakeholders"),recommended_workflows=("campaign.default",)),
    SituationTemplate("writing","writing",("purpose","audience"),("source_material","format","constraints"),recommended_workflows=("writing.default",)),
    SituationTemplate("repository_repair","repository",("objective","repository"),("failure","constraints"),recommended_workflows=("repository_repair.default",)),
    SituationTemplate("living_world","world",("scene","participants"),("location","pressures","unknowns"),recommended_workflows=("living_world.default",)),
)

WORKFLOWS = (
    Workflow("research.default",1,"Evidence-grounded inquiry",("research",),(
        WorkflowStage("question",next_stages=("evidence",)), WorkflowStage("evidence",("question",),("contradictions",)), WorkflowStage("contradictions",("evidence",),("synthesis",)), WorkflowStage("synthesis",("contradictions",),completion_requires=("question",)),)),
    Workflow("production_brief.default",1,"Produce a source-constrained production brief",("production_brief",),(
        WorkflowStage("objective",next_stages=("audience",)), WorkflowStage("audience",("objective",),("requirements",)), WorkflowStage("requirements",("audience",),("brief",)), WorkflowStage("brief",("requirements",),completion_requires=("objective","audience")),)),
    Workflow("campaign.default",1,"Develop a campaign",("campaign",),(WorkflowStage("objective",next_stages=("audience",)),WorkflowStage("audience",("objective",),("strategy",)),WorkflowStage("strategy",("audience",),completion_requires=("objective","audience")),)),
    Workflow("writing.default",1,"Create source-aware writing",("writing",),(WorkflowStage("purpose",next_stages=("draft",)),WorkflowStage("draft",("purpose",),("verify",)),WorkflowStage("verify",("draft",),completion_requires=("purpose",)),)),
    Workflow("repository_repair.default",1,"Reproduce, repair and verify a bounded repository defect",("repository_repair",),(WorkflowStage("reproduce",next_stages=("isolate",)),WorkflowStage("isolate",("reproduce",),("repair",)),WorkflowStage("repair",("isolate",),("test",)),WorkflowStage("test",("repair",),completion_requires=("reproduce","repair")),)),
    Workflow("living_world.default",1,"Continue a consequential living-world situation",("living_world",),(WorkflowStage("orient",next_stages=("act",)),WorkflowStage("act",("orient",),("consequence",)),WorkflowStage("consequence",("act",),completion_requires=("orient","act")),)),
)

def install_defaults(service):
    from .service import SituationError
    for kind, records, definitions, register in (
        ('template', service.templates, TEMPLATES, service.register_template),
        ('workflow', service.workflows, WORKFLOWS, service.register_workflow),
    ):
        for definition in definitions:
            key = getattr(definition, kind + '_id')
            if key in records:
                if records[key] != definition:
                    raise SituationError('stored ' + kind + ' conflicts with default: ' + key)
            else:
                register(definition)
    return service

