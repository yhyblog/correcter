"""The effective natural horizon and the corrective commitment are separate."""
class HorizonQueue:
    def __init__(self,normal_H,method):
        assert normal_H in (20,30) and method in ('N','R','Post','Velocity')
        self.normal_H=normal_H;self.method=method;self.raw=None;self.age=0;self.limit=normal_H
        self.locked_until=0;self.event=None;self.intervention=False
    def needs_plan(self):return self.raw is None or self.age>=self.limit
    def natural(self,raw,step):
        assert self.needs_plan() and len(raw)==30
        if self.intervention:
            assert step>=self.locked_until and self.age==10
            self.event.update(restore_normal_H=self.normal_H,restored_at_step=step,intervention_tail_discarded=True,new_natural_sample=True)
        self.raw=raw;self.age=0;self.limit=self.normal_H;self.intervention=False;self.event=None
    def can_monitor(self,step,frames,actions):
        return self.method!='N' and not self.intervention and step>=self.locked_until and step%5==0 and frames>=5 and actions>=4 and self.age>0 and self.limit-self.age>=5 and step+10<=300
    def intervene(self,raw,step,event):
        assert self.method!='N' and not self.intervention and step>=self.locked_until and len(raw)==30
        self.raw=raw;self.age=0;self.limit=10;self.locked_until=step+10;self.intervention=True;self.event=event
        event.update(C=10,commit_until=self.locked_until,commitment_executed=0,commitment_complete=False,restore_normal_H=self.normal_H,restored_at_step=None,intervention_tail_discarded=False,new_natural_sample=False)
    def action(self):
        assert self.raw is not None and self.age<self.limit
        return self.raw[self.age]
    def advanced(self,step):
        self.age+=1
        if self.intervention:
            self.event['commitment_executed']+=1
            if self.age==10:
                assert step+1==self.locked_until
                self.event['commitment_complete']=True
