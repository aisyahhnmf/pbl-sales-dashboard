# api/ml_loader.py
import pickle
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_DIR = os.path.join(BASE_DIR, 'models')

MODEL_MAP = {
    "Furniture"      : "final_omp_furniture.pkl",
    "Office Supplies": "final_arima_office_supplies.pkl",
    "Technology"     : "final_theta_technology.pkl"
}

FORECAST_MAP = {
    "Furniture"      : os.path.join("forecast", "forecast_omp_furniture.pkl"),
    "Office Supplies": os.path.join("forecast", "forecast_arima_office_supplies.pkl"),
    "Technology"     : os.path.join("forecast", "forecast_theta_technology.pkl")
}

def load_model_data(category: str) -> dict:
    if category not in MODEL_MAP:
        raise ValueError(f"Kategori '{category}' tidak valid")
    
    filepath = os.path.join(MODEL_DIR, MODEL_MAP[category])
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File tidak ditemukan: {filepath}")
    
    with open(filepath, 'rb') as f:
        raw_data = pickle.load(f)
    
    # JIKA raw_data bukan dictionary (misal langsung object model), bungkus ke dalam dict
    if not isinstance(raw_data, dict):
        return {
            "model": raw_data,
            "type": "omp" if category == "Furniture" else "unknown",
            "params": {},
            "val_metrics": {},
            "test_metrics": {}
        }
        
    # Jika sudah berbentuk dict, pastikan key penting di dalamnya aman menggunakan .get()
    return {
        "model": raw_data.get("model"),
        "type": raw_data.get("type", "omp" if category == "Furniture" else "unknown"),
        "params": raw_data.get("params", {}),
        "val_metrics": raw_data.get("val_metrics", {}),
        "test_metrics": raw_data.get("test_metrics", {})
    }

def load_forecast_data(category: str) -> dict:
    if category not in FORECAST_MAP:
        raise ValueError(f"Kategori '{category}' tidak valid")
    
    filepath = os.path.join(MODEL_DIR, FORECAST_MAP[category])
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File tidak ditemukan: {filepath}")
    
    with open(filepath, 'rb') as f:
        raw_data = pickle.load(f)
        
    # JIKA raw_data bukan dictionary, buat penanganan dasar
    if not isinstance(raw_data, dict):
        raise ValueError(f"Format data forecast di file .pkl {category} harus berupa dictionary.")

    # Ambil nilai forecast_values sebagai pondasi utama
    forecast_values = raw_data.get("forecast_values", [])

    # PENGAMAN UTAMA: OMP Furniture biasanya tidak punya lower dan upper bound.
    # Jika tidak ada, kita samakan dengan forecast_values agar perulangan di predict.py tidak crash.
    return {
        "forecast_values": forecast_values,
        "forecast_periods": raw_data.get("forecast_periods", []),
        "type": raw_data.get("type", "omp" if category == "Furniture" else "unknown"),
        "lower": raw_data.get("lower", forecast_values),
        "upper": raw_data.get("upper", forecast_values)
    }