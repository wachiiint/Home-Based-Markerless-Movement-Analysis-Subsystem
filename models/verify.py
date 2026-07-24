import onnxruntime as ort, numpy as np, shutil, os, tempfile
d = tempfile.mkdtemp()
shutil.copy('motionbert_lite_sim.onnx', d)
s = ort.InferenceSession(os.path.join(d,'motionbert_lite_sim.onnx'), providers=['CPUExecutionProvider'])
print(s.run(None, {'input_2d': np.random.randn(1,243,17,3).astype(np.float32)})[0].shape)
print('self-contained OK')