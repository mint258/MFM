# ------------ utils_debug.py ------------
import logging, os, torch, math, functools, inspect

_DEBUG_FLAG = False        # 全局私有变量


def set_debug(flag: bool):
    """
    在程序开始（如 main()）处调用一次，根据 CLI 参数设置。
    """
    global _DEBUG_FLAG
    _DEBUG_FLAG = bool(flag)
    # 统一 logging 等级
    logging.getLogger().setLevel(logging.DEBUG if _DEBUG_FLAG else logging.INFO)
    if _DEBUG_FLAG:
        logging.debug(">>>> GLOBAL DEBUG MODE IS ON <<<<")      # 提示


def is_debug() -> bool:
    """各模块用 is_debug() 判断是否输出调试信息"""
    return _DEBUG_FLAG
# ----------------------------------------

IS_NAN_DEBUG = bool(int(os.getenv('NAN_DEBUG', '0')))

def _bad(t: torch.Tensor):
    return torch.isnan(t).any() or torch.isinf(t).any()

# ---------- 安全数学算子 ----------
def safe_norm(v, dim=-1, keepdim=False, eps=1e-6):
    return torch.linalg.norm(v, dim=dim, keepdim=keepdim) + eps

def safe_acos(x, eps=1e-6):
    return torch.acos(torch.clamp(x, -1.+eps, 1.-eps))

def safe_exp(x, clip=20.0):
    return torch.exp(x.clamp(max=clip))

def safe_log1p(x, eps=1e-6):
    return torch.log1p(torch.clamp_min(x, eps))

# ---------- Hook 注册 ----------
def register_nan_hooks(module, prefix=''):
    """给 module 及其所有子模块 + 参数安装 forward/grad hook"""
    for name, sub in module.named_modules():
        tag = f'{prefix}{name}' if name else prefix or sub.__class__.__name__

        # forward 输出检测
        if IS_NAN_DEBUG:
            def _fwd_hook(mod, inp, out, t=tag):
                if isinstance(out, torch.Tensor) and _bad(out):
                    logging.error(f'🔥 NaN in FORWARD → {t}')
                    raise RuntimeError('NaN (forward)')
            sub.register_forward_hook(_fwd_hook)

    if IS_NAN_DEBUG:
        for pname, p in module.named_parameters():
            if not p.requires_grad:
                continue
            def _grad_hook(grad, t=f'{prefix}{pname}'):
                if _bad(grad):
                    logging.error(f'💥 NaN in GRAD → {t}')
                    raise RuntimeError('NaN (backward)')
                return grad
            p.register_hook(_grad_hook)