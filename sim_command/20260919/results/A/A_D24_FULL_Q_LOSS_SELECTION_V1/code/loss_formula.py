def require(ok,message):
    if not ok:raise ValueError(message)

def e1_loss(logits,outcomes,*,candidate_weights,gain_weights,pair_weights,gain_enabled,pair_enabled):
    """Same source means/alias weights and probability differences as the frozen core."""
    import torch
    from torch.nn import functional as F
    require(logits.ndim==2 and logits.shape[1]==13 and outcomes.shape==(*logits.shape,4),'Expected source/13 candidates/4 outcomes')
    cw=torch.as_tensor(candidate_weights,device=logits.device,dtype=logits.dtype)
    gw=torch.as_tensor(gain_weights,device=logits.device,dtype=logits.dtype)
    pw=torch.as_tensor(pair_weights,device=logits.device,dtype=logits.dtype)
    require(cw.shape==gw.shape==logits.shape and pw.shape==(len(logits),5),'Invalid alias weights')
    require(bool(torch.isfinite(logits).all()),'Nonfinite logits')
    require(bool(((outcomes==0)|(outcomes==1)).all()),'E1 requires all four real binary outcomes')
    for weight in (cw,gw,pw):require(bool(torch.isfinite(weight).all()) and bool(((weight>=0)&(weight<=1)).all()),'Invalid weights')
    require(bool((cw[:,0]>0).all()) and bool((gw[:,0]==0).all()),'a0 must be included in BCE and excluded from gain')
    y=outcomes.to(logits.dtype).mean(-1);p=logits.sigmoid()
    def average(value,weight):
        denominator=weight.sum(-1)
        return ((value*weight).sum(-1)/torch.where(denominator>0,denominator,torch.ones_like(denominator))).mean()
    bce=average(F.binary_cross_entropy_with_logits(logits,y,reduction='none'),cw)
    gain=average(((p-p[:,:1])-(y-y[:,:1])).square(),gw)
    pairs=((1,2),(3,4),(5,6),(7,8),(11,12))
    difference=torch.stack([(p[:,a]-p[:,b])-(y[:,a]-y[:,b]) for a,b in pairs],-1)
    pair=average(difference.square(),pw)
    return {'loss':bce+int(gain_enabled)*gain+.5*int(pair_enabled)*pair,'bce':bce,'gain_mse':gain,'pair_mse':pair}
