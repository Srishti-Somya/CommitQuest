"""Demonstration script to train an ARIMA/SARIMAX model on a user's contribution time series.

This script:
 - Fetches contribution calendar for a given date range
 - Builds a daily series (fills missing days with zeros)
 - Optionally resamples to weekly/monthly
 - Splits into train/test
 - Runs pmdarima.auto_arima on the training set to select orders
 - Fits a SARIMAX on training data
 - Evaluates on test set (MAE/RMSE)
 - Saves the fitted model with joblib

Usage:
  python3 scripts/train_arima_demo.py <username> <token> <from_date> <to_date> --model out.pkl

Notes:
 - Requires pmdarima and statsmodels (these are in requirements.txt).
 - This is a demo for a single-user dataset; for production you should add cross-validation, hyperparameter tuning, and persistence.
"""
import argparse
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error

from utils.fetch_github_data import fetch_data_for_duration
from utils.arima_predictor import contributions_weeks_to_series, fit_auto_arima
from statsmodels.tsa.statespace.sarimax import SARIMAX


def train_and_evaluate(series: pd.Series, test_size: int = 30, seasonal_m: int = 7):
    # Ensure series sorted by date
    series = series.sort_index()
    if len(series) < test_size + 10:
        raise ValueError("Not enough data for the requested test size; need at least test_size+10 observations")

    train = series.iloc[:-test_size]
    test = series.iloc[-test_size:]

    print(f"Train length: {len(train)}, Test length: {len(test)}")

    # Auto ARIMA to choose orders on train set
    am = fit_auto_arima(train, seasonal=True, m=seasonal_m)
    print("Auto-ARIMA chosen order:", am.order, "seasonal_order:", am.seasonal_order)

    # Fit SARIMAX on train
    order = am.order
    seasonal_order = am.seasonal_order
    model = SARIMAX(train, order=order, seasonal_order=seasonal_order, enforce_stationarity=False, enforce_invertibility=False)
    res = model.fit(disp=False)

    # Forecast test_size steps
    pred = res.get_forecast(steps=test_size)
    ypred = pred.predicted_mean

    mae = mean_absolute_error(test, ypred)
    rmse = np.sqrt(mean_squared_error(test, ypred))
    print(f"Test MAE: {mae:.4f}, RMSE: {rmse:.4f}")

    return res, mae, rmse


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("username")
    parser.add_argument("token")
    parser.add_argument("from_date")
    parser.add_argument("to_date")
    parser.add_argument("--model", dest="model_out", help="Output file to save fitted model (joblib)")
    parser.add_argument("--test-size", dest="test_size", type=int, default=30)
    parser.add_argument("--seasonal-m", dest="m", type=int, default=7)
    args = parser.parse_args()

    data = fetch_data_for_duration(args.username, args.token, args.from_date, args.to_date)
    if not data or data.get("errors"):
        print("Error fetching data:", data)
        return

    weeks = data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
    series = contributions_weeks_to_series(weeks)
    if series.empty:
        print("No contribution data available for the given range.")
        return

    # Optional: aggregate by week/month instead of daily (uncomment to use)
    # series = series.resample('W').sum()

    try:
        res, mae, rmse = train_and_evaluate(series, test_size=args.test_size, seasonal_m=args.m)
    except Exception as e:
        print("Training failed:", e)
        return

    if args.model_out:
        joblib.dump(res, args.model_out)
        print(f"Saved fitted model to {args.model_out}")


if __name__ == "__main__":
    main()
