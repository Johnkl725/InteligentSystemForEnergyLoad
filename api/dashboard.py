"""
Dashboard API endpoints for Energy Forecast Agent
Provides performance metrics and comparison data
"""

from fastapi import APIRouter, HTTPException, Query
from typing import List, Dict, Any
from datetime import datetime, timedelta
import logging
from database import get_db_connection

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
logger = logging.getLogger(__name__)

@router.get("/performance/summary")
async def get_performance_summary():
    """
    Get overall performance summary of the forecasting model.
    Returns metrics like MAE, RMSE, MAPE for different time periods.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get overall statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as total_predictions,
                AVG(ABS(actual_energy_mw - predicted_energy_mw)) as mae,
                SQRT(AVG(POWER(actual_energy_mw - predicted_energy_mw, 2))) as rmse,
                AVG(ABS((actual_energy_mw - predicted_energy_mw) / actual_energy_mw) * 100) as mape
            FROM energy_forecasts
            WHERE actual_energy_mw IS NOT NULL
        """)
        
        overall = cursor.fetchone()
        
        # Get last 24 hours statistics
        cursor.execute("""
            SELECT 
                COUNT(*) as predictions_24h,
                AVG(ABS(actual_energy_mw - predicted_energy_mw)) as mae_24h,
                SQRT(AVG(POWER(actual_energy_mw - predicted_energy_mw, 2))) as rmse_24h
            FROM energy_forecasts
            WHERE actual_energy_mw IS NOT NULL
                AND timestamp >= NOW() - INTERVAL '24 hours'
        """)
        
        last_24h = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        return {
            "overall": {
                "total_predictions": overall['total_predictions'] or 0,
                "mae": round(float(overall['mae'] or 0), 2),
                "rmse": round(float(overall['rmse'] or 0), 2),
                "mape": round(float(overall['mape'] or 0), 2)
            },
            "last_24h": {
                "predictions": last_24h['predictions_24h'] or 0,
                "mae": round(float(last_24h['mae_24h'] or 0), 2),
                "rmse": round(float(last_24h['rmse_24h'] or 0), 2)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting performance summary: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance/comparison")
async def get_prediction_vs_actual(
    hours: int = Query(24, ge=1, le=168, description="Number of hours to retrieve")
):
    """
    Get predicted vs actual energy values for comparison.
    Returns time series data for the specified number of hours.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                timestamp,
                predicted_energy_mw,
                actual_energy_mw,
                ABS(actual_energy_mw - predicted_energy_mw) as error
            FROM energy_forecasts
            WHERE actual_energy_mw IS NOT NULL
                AND timestamp >= NOW() - INTERVAL '%s hours'
            ORDER BY timestamp
        """, (hours,))
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        if not rows:
            return {
                "timestamps": [],
                "predicted": [],
                "actual": [],
                "errors": [],
                "statistics": {
                    "mean_error": 0,
                    "max_error": 0,
                    "min_error": 0,
                    "std_error": 0
                }
            }
        
        timestamps = [row['timestamp'].isoformat() for row in rows]
        predicted = [float(row['predicted_energy_mw']) for row in rows]
        actual = [float(row['actual_energy_mw']) for row in rows]
        errors = [float(row['error']) for row in rows]
        
        return {
            "timestamps": timestamps,
            "predicted": predicted,
            "actual": actual,
            "errors": errors,
            "statistics": {
                "mean_error": round(sum(errors) / len(errors), 2),
                "max_error": round(max(errors), 2),
                "min_error": round(min(errors), 2),
                "std_error": round((sum((e - sum(errors)/len(errors))**2 for e in errors) / len(errors))**0.5, 2)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting prediction comparison: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/performance/by-hour")
async def get_performance_by_hour():
    """
    Get performance metrics grouped by hour of day.
    Useful to identify if model performs better at certain times.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                EXTRACT(HOUR FROM timestamp) as hour,
                COUNT(*) as predictions,
                AVG(ABS(actual_energy_mw - predicted_energy_mw)) as mae,
                SQRT(AVG(POWER(actual_energy_mw - predicted_energy_mw, 2))) as rmse
            FROM energy_forecasts
            WHERE actual_energy_mw IS NOT NULL
            GROUP BY EXTRACT(HOUR FROM timestamp)
            ORDER BY hour
        """)
        
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        
        return {
            "hours": [int(row['hour']) for row in rows],
            "predictions": [int(row['predictions']) for row in rows],
            "mae": [round(float(row['mae']), 2) for row in rows],
            "rmse": [round(float(row['rmse']), 2) for row in rows]
        }
        
    except Exception as e:
        logger.error(f"Error getting performance by hour: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations/latest")
async def get_latest_recommendations():
    """
    Get latest recommendations from the monitoring agent.
    Returns actionable insights based on recent model performance.
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get recent worst predictions
        cursor.execute("""
            SELECT 
                timestamp,
                predicted_energy_mw,
                actual_energy_mw,
                ABS(actual_energy_mw - predicted_energy_mw) as error,
                ABS((actual_energy_mw - predicted_energy_mw) / actual_energy_mw * 100) as error_pct
            FROM energy_forecasts
            WHERE actual_energy_mw IS NOT NULL
            ORDER BY error DESC
            LIMIT 5
        """)
        
        worst_predictions = cursor.fetchall()
        
        # Get recent performance trend
        cursor.execute("""
            SELECT 
                DATE(timestamp) as date,
                AVG(ABS(actual_energy_mw - predicted_energy_mw)) as mae
            FROM energy_forecasts
            WHERE actual_energy_mw IS NOT NULL
                AND timestamp >= NOW() - INTERVAL '7 days'
            GROUP BY DATE(timestamp)
            ORDER BY date
        """)
        
        trend = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Generate recommendations
        recommendations = []
        
        if worst_predictions:
            avg_error = sum(float(p['error']) for p in worst_predictions) / len(worst_predictions)
            if avg_error > 10:
                recommendations.append({
                    "type": "warning",
                    "message": f"High prediction errors detected (avg: {avg_error:.2f} MW)",
                    "action": "Consider retraining the model with recent data"
                })
        
        if len(trend) >= 2:
            mae_trend = [float(t['mae']) for t in trend]
            if mae_trend[-1] > mae_trend[0] * 1.2:
                recommendations.append({
                    "type": "alert",
                    "message": "Model performance is degrading over time",
                    "action": "Review feature engineering and data quality"
                })
        
        if not recommendations:
            recommendations.append({
                "type": "success",
                "message": "Model performance is stable",
                "action": "Continue monitoring"
            })
        
        return {
            "recommendations": recommendations,
            "worst_predictions": [
                {
                    "timestamp": p['timestamp'].isoformat(),
                    "predicted": float(p['predicted_energy_mw']),
                    "actual": float(p['actual_energy_mw']),
                    "error": float(p['error']),
                    "error_pct": round(float(p['error_pct']), 2)
                }
                for p in worst_predictions
            ]
        }
        
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))
