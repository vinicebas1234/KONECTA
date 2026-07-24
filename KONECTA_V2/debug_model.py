import pickle
import numpy as np

norm_path = r"C:\KONECTA\OCR\modelos\variancia_pooled_estatica.pkl"

with open(norm_path, 'rb') as f:
    data = pickle.load(f)
    print(f'Tipo: {type(data)}')
    if isinstance(data, dict):
        print(f'Chaves: {list(data.keys())}')
        for k, v in data.items():
            print(f'  {k}: tipo={type(v)}, shape={getattr(v, "shape", "N/A")}')
            if isinstance(v, dict):
                print(f'    Dict keys: {list(v.keys())}')
    else:
        print(f'Shape: {data.shape}')
