#!/usr/bin/env bash
# ESSAI SEULEMENT (accord écrit de NT, 16/11/2026 : « Ok » à la liste) : télécharge ComfyUI portable (GPL-3, outil à part) et
# TRELLIS.2 compressé avec ses accessoires dans D:\Atelya-Essais\comfyui, puis vérifie chaque fichier (taille et SHA256 officiels).
# Reprend là où il s'est arrêté (curl -C -). S'arrête au premier échec avec une ligne « PLANTÉ … ». Pixal3D n'est PAS téléchargé.
set -u
D=/d/Atelya-Essais/comfyui/telechargements
mkdir -p "$D" || { echo "PLANTÉ : dossier"; exit 1; }
cd "$D" || { echo "PLANTÉ : dossier"; exit 1; }

prendre() { # nom  adresse  taille  sha256
  local nom="$1" url="$2" taille="$3" sha="$4"
  if [ -f "$nom" ] && [ "$(stat -c %s "$nom")" = "$taille" ]; then echo "déjà là : $nom"; else
    echo "téléchargement : $nom ($((taille / 1000000)) Mo)"
    curl -sS -L -C - --retry 8 --retry-delay 5 --max-time 7200 -o "$nom" "$url" || { echo "PLANTÉ : téléchargement de $nom"; exit 1; }
  fi
  [ "$(stat -c %s "$nom")" = "$taille" ] || { echo "PLANTÉ : taille de $nom = $(stat -c %s "$nom"), attendu $taille"; exit 1; }
  local lu; lu=$(sha256sum "$nom" | cut -d' ' -f1)
  [ "$lu" = "$sha" ] || { echo "PLANTÉ : empreinte de $nom = $lu, attendu $sha"; exit 1; }
  echo "vérifié : $nom"
}

HF=https://huggingface.co
prendre ComfyUI_windows_portable_nvidia_cu126.7z https://github.com/Comfy-Org/ComfyUI/releases/download/v0.45.0/ComfyUI_windows_portable_nvidia_cu126.7z 1962803660 e7d1be2bd81deec3f46a89e29b8c6826f45c05609f29d6681d7876f687d69d29
prendre birefnet.safetensors $HF/Comfy-Org/BiRefNet/resolve/main/background_removal/birefnet.safetensors 444473596 9ab37426bf4de0567af6b5d21b16151357149139362e6e8992021b8ce356a154
prendre trellis_2_texture_vae_bf16.safetensors $HF/Comfy-Org/TRELLIS.2/resolve/main/vae/trellis_2_texture_vae_bf16.safetensors 948461364 714e5ebf094a610e12a8e3b5175c18a62f37f6ea4218acb6073644456b73ab0e
prendre trellis_2_shape_vae_bf16.safetensors $HF/Comfy-Org/TRELLIS.2/resolve/main/vae/trellis_2_shape_vae_bf16.safetensors 1095844024 de0cb4949a76c59ee5c091a995a69bcc8c51d5aeda939f0c641a50d2a72341f4
prendre dino_v3_vit_l.safetensors $HF/Comfy-Org/TRELLIS.2/resolve/main/clip_vision/dino_v3_vit_l.safetensors 1212559776 5cb785e458de7c460579082418af81f5c62380c181599344bdc60898c63468ee
prendre trellis_2_int8_convrot.safetensors $HF/Comfy-Org/TRELLIS.2/resolve/main/diffusion_models/trellis_2_int8_convrot.safetensors 5253048192 d01952ad137213f6a868f86b6b877026276f84af5eec23069217475a0bad3a31
echo "TOUT EST TÉLÉCHARGÉ ET VÉRIFIÉ"
