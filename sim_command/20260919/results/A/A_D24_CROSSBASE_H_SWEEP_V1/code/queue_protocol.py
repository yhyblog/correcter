"""Pure CPU queue state used by the real native rollout loop."""
class NativeQueue:
    def __init__(self, normal_H, method, raw_length=50):
        if type(normal_H) is not int or not 10<=normal_H<=raw_length:raise ValueError('normal H outside raw plan')
        if method not in ('N','R','Post','Velocity'):raise ValueError('method')
        self.H=normal_H;self.method=method;self.C=10;self.raw_length=raw_length
        self.raw=None;self.age=0;self.limit=normal_H;self.locked_until=0;self.is_commitment=False;self.tail_discards=0;self.restorations=0
    def needs_refill(self):return self.raw is None or self.age>=self.limit
    def refill(self, raw):
        if len(raw)!=self.raw_length:raise ValueError('native raw length changed')
        if self.is_commitment:self.tail_discards+=1;self.restorations+=1
        self.raw=raw;self.age=0;self.limit=self.H;self.is_commitment=False
    def monitor_due(self,t):
        return self.method!='N' and t>=self.locked_until and t%5==0 and min(self.limit-self.age,300-t)>=5
    def legal_cut(self,t,history_count,action_count):
        return self.monitor_due(t) and history_count>=5 and action_count>=4 and self.age>0 and t+self.C<=300
    def commit(self,raw,t):
        if self.method=='N' or not self.legal_cut(t,5,4):raise ValueError('illegal commitment')
        if len(raw)!=self.raw_length:raise ValueError('raw tail changed length')
        self.raw=raw;self.age=0;self.limit=self.C;self.locked_until=t+self.C;self.is_commitment=True
    def action(self):
        if self.needs_refill():raise ValueError('empty queue')
        action=self.raw[self.age].copy();self.age+=1;return action
