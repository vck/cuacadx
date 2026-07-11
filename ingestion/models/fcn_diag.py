"""Phase 0: Residual hypothesis direct test. Run 28 steps with fix applied."""
import logging, sys
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
import torch
import numpy as np
from scipy.ndimage import gaussian_filter, zoom
from earth2studio.models.auto.package import Package
from earth2studio.models.px.fcn import FCN
from pathlib import Path

MODEL_DIR = Path("models/fourcastnet")
pkg = Package(str(MODEL_DIR.resolve()))
model = FCN.load_model(pkg)
model.eval()
center, scale = model.center.cpu(), model.scale.cpu()

# Test 1: zero input in normalized space
print("=== Test 1: Zero normalized input ===")
x = torch.zeros(1, 1, 26, 720, 1440)
with torch.inference_mode():
    out = model._forward(x)
    print(f"  range=[{out.min().item():.0f},{out.max().item():.0f}] mean={out.mean().item():.0f}")
    print(f"  t2m@eq={out[0,0,2,360,720].item()-273.15:.1f}°C")

# Test 2: Try residual fix
print("\n=== Test 2: Residual fix (x = x + model(x_norm)) ===")
class FCNResidual(FCN):
    def _forward(self, x):
        x = x.squeeze(1)
        xn = (x - self.center) / self.scale
        dx = self.model(xn)
        x = self.scale * (xn + dx) + self.center
        x = x.unsqueeze(1)
        return x

model2 = FCNResidual(model.model, model.center, model.scale)
model2.eval()

# Stub IC
rng = np.random.RandomState(42)
channels = []
cv = center.numpy().ravel()
sv = scale.numpy().ravel()
for v in range(26):
    coarse = rng.randn(46, 90)
    smooth = zoom(gaussian_filter(coarse, 1.5), (720/46, 1440/90), order=1)
    smooth = smooth / smooth.std() * 0.5
    channels.append((smooth * sv[v] + cv[v]).astype(np.float32))

ic = torch.from_numpy(np.stack(channels, axis=0)).unsqueeze(0).unsqueeze(0)

import time
with torch.inference_mode():
    x = ic
    for step in range(28):
        t0 = time.perf_counter()
        x = model2._forward(x)
        dt = time.perf_counter() - t0
        t2m_k = x[0, 0, 2, 360, 720].item()
        arr = x[0, 0].numpy()
        print(f"  +{(step+1)*6:3d}h  {dt:.2f}s  t2m@eq={t2m_k-273.15:.1f}°C  "
              f"range=[{arr.min():.0f},{arr.max():.0f}]"
              f"  mean|delta|={arr.std():.1f}")
        if step >= 1 and (arr.max() > 1e6 or arr.min() < -1e6):
            print("  *** DIVERGED ***")
            break
