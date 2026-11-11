"""Les COULEURS dans la pellicule d'Unreal 5.8 (11/11/2026) : le chemin complet d'une couleur linéaire jusqu'à l'écran, recopié
des fichiers de calcul fournis avec le moteur (Engine/Shaders/Private : PostProcessCombineLUTs.usf, TonemapCommon.ush,
ACES/ACESCommon.ush) : « expansion de gamme » des couleurs saturées, correction des bleus, renfort des rouges et « lueur » de
l'ACES, désaturation avant et après la courbe filmique, retour en sRGB. Sur les gris, il retombe exactement sur
moteur.photographe.courbe_unreal.

Pourquoi : régler les couleurs d'Unreal sur celles de Blender (AgX) SANS lancer Unreal, sur un nuancier de 163 couleurs passé
dans AgX de Blender 5.2 (tests/donnees/nuancier_agx_blender52.json). Résultat (photographe.PELLICULE_COULEURS) : écart moyen
8,6/255 avec les réglages d'usine → 5,7/255, la courbe des gris restant celle de la PELLICULE.
"""

import numpy as np

M = lambda *v: np.array(v, dtype=float).reshape(3, 3)
AP0_2_XYZ = M(0.9525523959, 0.0, 0.0000936786, 0.3439664498, 0.7281660966, -0.0721325464, 0.0, 0.0, 1.0088251844)
XYZ_2_AP0 = M(1.0498110175, 0.0, -0.0000974845, -0.4959030231, 1.3733130458, 0.0982400361, 0.0, 0.0, 0.9912520182)
AP1_2_XYZ = M(0.6624541811, 0.1340042065, 0.1561876870, 0.2722287168, 0.6740817658, 0.0536895174, -0.0055746495, 0.0040607335, 1.0103391003)
XYZ_2_AP1 = M(1.6410233797, -0.3248032942, -0.2364246952, -0.6636628587, 1.6153315917, 0.0167563477, 0.0117218943, -0.0082844420, 0.9883948585)
D65_2_D60 = M(1.0130349146, 0.0061052578, -0.0149709436, 0.0076982301, 0.9981633521, -0.0050320385, -0.0028413174, 0.0046851567, 0.9245061375)
D60_2_D65 = M(0.9872240087, -0.0061132286, 0.0159532883, -0.0075983718, 1.0018614847, 0.0053300358, 0.0030725771, -0.0050959615, 1.0816806031)
SRGB_2_XYZ = M(0.4123907993, 0.3575843394, 0.1804807884, 0.2126390059, 0.7151686788, 0.0721923154, 0.0193308187, 0.1191947798, 0.9505321522)
XYZ_2_SRGB = M(3.2409699419, -1.5373831776, -0.4986107603, -0.9692436363, 1.8759675015, 0.0415550574, 0.0556300797, -0.2039769589, 1.0569715142)
AP1_RGB2Y = np.array([0.2722287168, 0.6740817658, 0.0536895174])
SRGB_2_AP1 = XYZ_2_AP1 @ D65_2_D60 @ SRGB_2_XYZ
AP1_2_SRGB = XYZ_2_SRGB @ D60_2_D65 @ AP1_2_XYZ
AP0_2_AP1 = XYZ_2_AP1 @ AP0_2_XYZ
AP1_2_AP0 = XYZ_2_AP0 @ AP1_2_XYZ
WIDE_2_XYZ = M(0.5441691, 0.2395926, 0.1666943, 0.2394656, 0.7021530, 0.0583814, -0.0023439, 0.0361834, 1.0552183)
EXPAND = (XYZ_2_AP1 @ WIDE_2_XYZ) @ AP1_2_SRGB
BLUE = M(0.9404372683, -0.0183068787, 0.0778696104, 0.0083786969, 0.8286599939, 0.1629613092, 0.0005471261, -0.0008833746, 1.0003362486)
BLUE_INV = M(1.06318, 0.0233956, -0.0865726, -0.0106337, 1.20632, -0.19569, -0.000590887, 0.00105248, 0.999538)
BLUE_AP1 = AP0_2_AP1 @ BLUE @ AP1_2_AP0
BLUE_INV_AP1 = AP0_2_AP1 @ BLUE_INV @ AP1_2_AP0


def _sat(c):
    mi, ma = c.min(1), c.max(1)
    return (np.maximum(ma, 1e-10) - np.maximum(mi, 1e-10)) / np.maximum(ma, 1e-2)


def _yc(c):
    r, g, b = c[:, 0], c[:, 1], c[:, 2]
    chroma = np.sqrt(np.maximum(b * (b - g) + g * (g - r) + r * (r - b), 0))
    return (b + g + r + 1.75 * chroma) / 3.0


def _sigmoid(x):
    t = np.maximum(1 - np.abs(0.5 * x), 0)
    return 0.5 * (1 + np.sign(x) * (1 - t * t))


def _glow(yc, gain, mid):
    return np.where(yc <= 2 / 3 * mid, gain, np.where(yc >= 2 * mid, 0.0, gain * (mid / np.maximum(yc, 1e-10) - 0.5)))


def _hue(c):
    egal = (c[:, 0] == c[:, 1]) & (c[:, 1] == c[:, 2])
    h = np.degrees(np.arctan2(np.sqrt(3) * (c[:, 1] - c[:, 2]), 2 * c[:, 0] - c[:, 1] - c[:, 2]))
    h = np.where(h < 0, h + 360, h)
    return np.where(egal, 0.0, np.clip(h, 0, 360))


def _smoothstep(a, b, x):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def film_tone_map(ap1, slope, toe, shoulder, black, white):
    ap0 = ap1 @ AP1_2_AP0.T
    sat = _sat(ap0)
    s = _sigmoid((sat - 0.4) / 0.2)
    ap0 = ap0 * (1 + _glow(_yc(ap0), 0.05 * s, 0.08))[:, None]
    h = _hue(ap0)
    hc = h - 0.0
    hc = np.where(hc < -180, hc + 360, np.where(hc > 180, hc - 360, hc))
    w = _smoothstep(0, 1, 1 - np.abs(2 * hc / 135.0)) ** 2
    ap0[:, 0] += w * sat * (0.03 - ap0[:, 0]) * (1 - 0.82)
    wc = np.maximum(ap0 @ AP0_2_AP1.T, 0)
    wc = (wc @ AP1_RGB2Y)[:, None] * (1 - 0.96) + wc * 0.96
    ts, ss = 1 + black - toe, 1 + white - shoulder
    if toe > 0.8:
        tm = (1 - toe - 0.18) / slope + np.log10(0.18)
    else:
        bt = (0.18 + black) / ts - 1
        tm = np.log10(0.18) - 0.5 * np.log((1 + bt) / (1 - bt)) * (ts / slope)
    sm = (1 - toe) / slope - tm
    shm = shoulder / slope - sm
    lc = np.log10(np.maximum(wc, 1e-10))
    st = slope * (lc + sm)
    tc = -black + 2 * ts / (1 + np.exp((-2 * slope / ts) * (lc - tm)))
    sc = (1 + white) - 2 * ss / (1 + np.exp((2 * slope / ss) * (lc - shm)))
    tc = np.where(lc < tm, tc, st)
    sc = np.where(lc > shm, sc, st)
    t = np.clip((lc - tm) / (shm - tm), 0, 1)
    t = (3 - 2 * t) * t * t
    tone = tc + (sc - tc) * t
    tone = (tone @ AP1_RGB2Y)[:, None] * (1 - 0.93) + tone * 0.93
    return np.maximum(tone, 0)


def affiche(lin, film, saturation=1.0, expand_gamut=1.0, blue_correction=0.6):
    """lin : N × 3 couleurs linéaires sRGB ; film : dict film_slope… ; renvoie N × 3 valeurs affichées sRGB (0..1)."""
    c = np.asarray(lin, float).reshape(-1, 3) @ SRGB_2_AP1.T
    luma = np.maximum(c @ AP1_RGB2Y, 1e-10)
    chroma = c / luma[:, None]
    d2 = ((chroma - 1) ** 2).sum(1)
    amt = (1 - 2 ** (-4 * d2)) * (1 - 2 ** (-4 * expand_gamut * luma ** 2))
    c = c + (c @ EXPAND.T - c) * amt[:, None]
    luma = c @ AP1_RGB2Y
    c = np.maximum(luma[:, None] + (c - luma[:, None]) * saturation, 0)
    c = c + (c @ BLUE_AP1.T - c) * blue_correction
    c = film_tone_map(c, film["film_slope"], film["film_toe"], film["film_shoulder"], film["film_black_clip"],
                      film["film_white_clip"])
    c = c + (c @ BLUE_INV_AP1.T - c) * blue_correction
    c = np.clip(np.maximum(c @ AP1_2_SRGB.T, 0), 0, 1)
    return np.where(c <= 0.0031308, 12.92 * c, 1.055 * c ** (1 / 2.4) - 0.055)
