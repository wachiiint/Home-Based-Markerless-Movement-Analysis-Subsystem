import argparse, torch
from lib.utils.tools import get_config
from lib.utils.learning import load_backbone

p = argparse.ArgumentParser()
p.add_argument("--config", required=True)
p.add_argument("--ckpt", required=True)
p.add_argument("--out", default="motionbert.onnx")
p.add_argument("--frames", type=int, default=243)   # max 243
p.add_argument("--opset", type=int, default=17)
args = p.parse_args()

cfg = get_config(args.config)
model = load_backbone(cfg)

ckpt = torch.load(args.ckpt, map_location="cpu", weights_only=False)
# Saved from an nn.DataParallel wrapper -> every key carries a "module." prefix
state = {k.replace("module.", "", 1): v for k, v in ckpt["model_pos"].items()}
missing, unexpected = model.load_state_dict(state, strict=False)
print("missing:", missing, "\nunexpected:", unexpected)
model.eval()

dummy = torch.randn(1, args.frames, 17, 3)
with torch.no_grad():
    ref = model(dummy)
print("torch out:", tuple(ref.shape))

torch.onnx.export(
    model, dummy, args.out,
    input_names=["input_2d"], output_names=["output_3d"],
    dynamic_axes={"input_2d":  {0: "batch", 1: "frames"},
                  "output_3d": {0: "batch", 1: "frames"}},
    opset_version=args.opset, do_constant_folding=True,
)
print("wrote", args.out)

# --- verify ---
import numpy as np, onnx, onnxruntime as ort
onnx.checker.check_model(onnx.load(args.out))
sess = ort.InferenceSession(args.out, providers=["CPUExecutionProvider"])
got = sess.run(None, {"input_2d": dummy.numpy()})[0]
print("max abs diff:", np.abs(got - ref.numpy()).max())

# Confirm the frame dim is genuinely dynamic and not frozen by the tracer
short = np.random.randn(1, 27, 17, 3).astype(np.float32)
print("27-frame out:", sess.run(None, {"input_2d": short})[0].shape)