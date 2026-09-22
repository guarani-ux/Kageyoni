"""Completion means a checked execution closed, not necessarily objective success."""
from dataclasses import dataclass
from enum import Enum
from ..engine import require

class Disposition(str,Enum):
    WAITING='waiting'
    BLOCKED='blocked'
    FAILED='failed'
    CANCELLED='cancelled'
    COMPLETED='completed'

class Objective(str,Enum):
    ACHIEVED='achieved'
    PARTIAL='partly_achieved'
    NOT_ACHIEVED='not_achieved'
    UNRESOLVED='unresolved'

@dataclass(frozen=True)
class Result:
    disposition: Disposition
    objective: Objective=Objective.UNRESOLVED
    reason: str=''
    resume_condition: str|None=None
    checks_passed: bool=False
    output: object=None
    def __post_init__(self):
        require(isinstance(self.disposition,Disposition),'typed disposition required')
        require(isinstance(self.objective,Objective),'typed objective required')
        require(type(self.checks_passed) is bool,'checks_passed must be boolean')
        require(isinstance(self.reason,str) and bool(self.reason.strip()),'result reason required')
        if self.disposition==Disposition.WAITING:
            require(isinstance(self.resume_condition,str) and bool(self.resume_condition.strip()),'waiting requires resume condition')
        if self.disposition==Disposition.COMPLETED:require(self.checks_passed,'completion requires checks')
        else:require(self.objective==Objective.UNRESOLVED,'nonterminal objective remains unresolved')

def close_required(children, *, checks_passed, objective=Objective.UNRESOLVED, output=None):
    require(type(checks_passed) is bool,'checks_passed must be boolean')
    require(all(isinstance(x,Result) for x in children),'untyped child result')
    for state in (Disposition.FAILED,Disposition.BLOCKED,Disposition.WAITING,Disposition.CANCELLED):
        child=next((x for x in children if x.disposition==state),None)
        if child:return Result(state,reason='Required child: '+child.reason,resume_condition=child.resume_condition)
    if not checks_passed:return Result(Disposition.FAILED,reason='Parent acceptance checks failed')
    return Result(Disposition.COMPLETED,objective=objective,reason='Required children closed and parent checks passed',checks_passed=True,output=output)
