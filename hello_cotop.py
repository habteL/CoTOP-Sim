import sys
import numpy as np
import torch
import matplotlib

print("=== CoTOP-Sim Environment Check ===")
print(f"Python    : {sys.version}")
print(f"NumPy     : {np.__version__}")
print(f"PyTorch   : {torch.__version__}")
print(f"Matplotlib: {matplotlib.__version__}")
print(f"CUDA      : {torch.cuda.is_available()}")
print()
print("All dependencies verified.")
print("CoTOP-Sim Sprint 0 complete.")