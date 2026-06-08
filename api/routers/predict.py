# api/routers/predict.py
from fastapi import APIRouter, HTTPException
from api.ml_loader import load_model_data, load_forecast_data
from api.schemas import PredictRequest, PredictResponse
import numpy as np
import logging

# Inisialisasi logger agar error asli kelihatan di terminal Railway
logger = logging.getLogger("uvicorn.error")

router = APIRouter(
    prefix="/predict",
    tags=["Forecasting"]
)

VALID_CATEGORIES = ["Furniture", "Office Supplies", "Technology"]


# ════════════════════════════════
#    LOGIC PREDICT PER MODEL TYPE
# ════════════════════════════════

def predict_omp(model_data: dict) -> float:
    """Prediksi untuk Furniture menggunakan OMP dengan pengaman"""
    try:
        model_tuple = model_data['model']
        omp_model   = model_tuple[0]   # OrthogonalMatchingPursuit
        scaler      = model_tuple[1]   # StandardScaler
        lag_values  = model_tuple[2]   # array nilai historis
        
        # Pengaman jika params atau n_lags tidak ada
        params = model_data.get('params', {})
        n_lags = params.get('n_lags', 12) # default 12 jika tidak ada

        # Pengaman jika data historis terlalu pendek
        if len(lag_values) < n_lags:
            n_lags = len(lag_values)

        last_lags = lag_values[-n_lags:].reshape(1, -1)
        X_scaled  = scaler.transform(last_lags)
        result    = omp_model.predict(X_scaled)
        return float(result[0])
    except Exception as e:
        logger.error(f"Gagal di fungsi predict_omp: {str(e)}", exc_info=True)
        raise e


def predict_arima(model_data: dict) -> float:
    """Prediksi untuk Office Supplies menggunakan ARIMA"""
    arima_result = model_data['model']
    forecast     = arima_result.forecast(steps=1)
    return float(forecast.iloc[0])


def predict_theta(model_data: dict) -> float:
    """Prediksi untuk Technology menggunakan Theta"""
    theta_result = model_data['model']
    forecast     = theta_result.forecast(steps=1)
    if hasattr(forecast, 'iloc'):
        return float(forecast.iloc[0])
    return float(forecast[0])


# ════════════════════════════════
#    ENDPOINT: PREDICT SALES
# ════════════════════════════════

@router.post(
    "/predict-sales",
    response_model=PredictResponse,
    summary="Predict Sales",
    description="Prediksi penjualan berdasarkan kategori produk"
)
async def predict_sales(data: PredictRequest):
    # Pengaman Case-Insensitive: Mencocokkan input kategori tanpa memedulikan huruf besar/kecil
    matched_category = next((c for c in VALID_CATEGORIES if c.lower() == data.category.lower().strip()), None)
    
    if not matched_category:
        raise HTTPException(
            status_code=404,
            detail=f"Kategori tidak valid. Pilih salah satu: {VALID_CATEGORIES}"
        )
    try:
        model_data = load_model_data(matched_category)
        model_type = model_data.get('type', 'unknown')

        if model_type == 'omp':
            predicted = predict_omp(model_data)
        elif model_type == 'arima':
            predicted = predict_arima(model_data)
        elif model_type == 'theta':
            predicted = predict_theta(model_data)
        else:
            raise ValueError(f"Tipe model '{model_type}' tidak dikenali")

        return PredictResponse(
            category=matched_category,
            predicted_sales=round(predicted, 2),
            model_used=model_type.upper()
        )

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"🚨 Error predict_sales untuk {data.category}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error prediksi: {str(e)}")


# ════════════════════════════════
#    ENDPOINT: FORECAST
# ════════════════════════════════

@router.get(
    "/forecast/{category}",
    summary="Get Forecast",
    description="Ambil hasil forecast per kategori produk"
)
async def get_forecast(category: str):
    # Pengaman Case-Insensitive: Menghindari error FileNotFoundError akibat perbedaan huruf besar/kecil di Linux Server
    matched_category = next((c for c in VALID_CATEGORIES if c.lower() == category.lower().strip()), None)
    
    if not matched_category:
        raise HTTPException(
            status_code=404,
            detail=f"Kategori tidak valid. Pilih: {VALID_CATEGORIES}"
        )
    try:
        data             = load_forecast_data(matched_category)
        forecast_values  = data.get('forecast_values', [])
        periods          = data.get('forecast_periods', [])
        
        # PENGAMAN CRITICAL: OMP biasanya tidak punya lower & upper bound.
        # Jika tidak ada, samakan nilainya dengan forecast_values agar tidak Null/Crash
        lower            = data.get('lower', forecast_values)
        upper            = data.get('upper', forecast_values)

        result = []
        for i in range(len(forecast_values)):
            # Ambil nilai batas, berikan fallback nilai asli jika index out of bound
            lbl = lower[i] if i < len(lower) else forecast_values[i]
            ubl = upper[i] if i < len(upper) else forecast_values[i]

            result.append({
                "period"        : str(periods[i]),
                "forecast_sales": round(float(forecast_values[i]), 2),
                "lower_bound"   : round(float(lbl), 2),
                "upper_bound"   : round(float(ubl), 2),
            })

        return {
            "category"     : matched_category,
            "model_used"   : data.get('type', 'unknown').upper(),
            "total_periods": len(result),
            "forecast"     : result
        }

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"🚨 Error get_forecast untuk {category}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error forecast: {str(e)}")


# ════════════════════════════════
#    ENDPOINT: MODEL METRICS
# ════════════════════════════════

@router.get(
    "/metrics/{category}",
    summary="Get Model Metrics",
    description="Ambil metrik evaluasi model (MAE, RMSE, MAPE, R2)"
)
async def get_metrics(category: str):
    # Pengaman Case-Insensitive: Menyamakan pencarian kategori ke load_model_data
    matched_category = next((c for c in VALID_CATEGORIES if c.lower() == category.lower().strip()), None)
    
    if not matched_category:
        raise HTTPException(
            status_code=404,
            detail=f"Kategori tidak valid. Pilih: {VALID_CATEGORIES}"
        )
    try:
        model_data = load_model_data(matched_category)
        
        # PENGAMAN: Jika dictionary metrik kosong, berikan dictionary kosong berisi pesan dummy
        val_metrics = model_data.get('val_metrics', {})
        if not val_metrics:
            val_metrics = {"MAE": 0.0, "RMSE": 0.0, "MAPE": 0.0, "R2": 0.0, "info": "Metrik tidak tersedia"}

        test_metrics = model_data.get('test_metrics', {})
        if not test_metrics:
            test_metrics = {"MAE": 0.0, "RMSE": 0.0, "MAPE": 0.0, "R2": 0.0, "info": "Metrik tidak tersedia"}

        return {
            "category"    : matched_category,
            "model_used"  : model_data.get('type', 'unknown').upper(),
            "params"      : model_data.get('params', {}),
            "val_metrics" : val_metrics,
            "test_metrics": test_metrics
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"🚨 Error get_metrics untuk {category}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error metrics: {str(e)}")