"""Normal execution H and intervention commitment C are distinct clocks."""
class HorizonQueue:
    def __init__(self, normal_H, raw_length=50, commitment=10):
        if normal_H not in (40,50) or normal_H>raw_length or commitment!=10:
            raise ValueError('outside B fixed H sweep')
        self.normal_H=normal_H;self.C=commitment;self.limit=normal_H
        self.age=0;self.locked_until=0;self.initialized=False
        self.commitment_event=None

    def needs_refill(self):
        return not self.initialized or self.age==self.limit

    def natural_refill(self, step):
        if self.commitment_event is not None:
            self.commitment_event.update(native_H_restored=True,native_restore_step=step,
                                         unused_intervention_tail_discarded=True)
            self.commitment_event=None
        self.age=0;self.limit=self.normal_H;self.initialized=True

    def monitor_due(self, step, method):
        return (method!='N' and step>=self.locked_until and step%5==0
                and min(self.limit-self.age,300-step)>=5)

    def legal_cut(self, step, history_frames, past_actions):
        return (history_frames>=5 and past_actions>=4 and self.age>0
                and self.limit-self.age>=5 and step+self.C<=300)

    def commit(self, step, event):
        self.age=0;self.limit=self.C;self.locked_until=step+self.C
        self.commitment_event=event
        event.update(commit_until=self.locked_until,commitment_C=self.C,
                     normal_H=self.normal_H,C10_steps_executed=0,C10_complete=False,
                     native_H_restored=False,native_restore_step=None)

    def executed(self):
        self.age+=1
        if self.age>self.limit:raise ValueError('execution queue overrun')
        if self.commitment_event is not None:
            self.commitment_event['C10_steps_executed']+=1
            self.commitment_event['C10_complete']=self.age==self.C
