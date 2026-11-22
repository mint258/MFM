"""Original strict encoder loader, copied unchanged from the specified follow-up tool dependency."""
def load_representation_encoder(checkpoint, *, device='cuda'):
    """Shared strict loading route for the P0 and follow-up representation studies."""
    import torch
    from phychem_mfm.phase1.v2_s_training import s_model
    payload=torch.load(checkpoint,map_location='cpu',weights_only=True)
    model,_=s_model('C1-0','three');state=payload['model']
    if any(k.startswith('structural.') for k in state):
        state={k.removeprefix('structural.'):v for k,v in state.items() if k.startswith('structural.')}
    model.load_state_dict(state)
    return model.encoder.to(device).eval(),payload
