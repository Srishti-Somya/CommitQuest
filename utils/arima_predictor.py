import warnings
from typing import Dict, Any

import pandas as pd
import numpy as np

try:
    import pmdarima as pm
    from statsmodels.tsa.statespace.sarimax import SARIMAX
except Exception:  # pragma: no cover - optional deps
    pm = None
    SARIMAX = None
from pandas.tseries.frequencies import to_offset


def contributions_weeks_to_series(weeks: list) -> pd.Series:
    """Convert GitHub GraphQL `weeks` structure into a daily pandas Series.

    Fills missing dates with zeros and returns a `pd.Series` indexed by `DatetimeIndex`.
    """
    days = [day for week in weeks for day in week.get("contributionDays", [])]
    if not days:
        return pd.Series(dtype=float)

    df = pd.DataFrame(days)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date").sort_index()
    s = df["contributionCount"].astype(float)

    idx = pd.date_range(start=s.index.min(), end=s.index.max(), freq="D")
    s = s.reindex(idx, fill_value=0)
    s.index.name = "date"
    return s


def fit_auto_arima(series: pd.Series, seasonal: bool = True, m: int = 7):
    if pm is None:
        raise RuntimeError("pmdarima is not installed")

    if len(series) < 10:
        raise ValueError("Not enough observations for auto_arima (need >=10)")

    warnings.filterwarnings("ignore")
    model = pm.auto_arima(
        series,
        seasonal=seasonal,
        m=m,
        error_action="ignore",
        suppress_warnings=True,
        stepwise=True,
        max_p=5,
        max_q=5,
        max_P=2,
        max_Q=2,
    )
    return model


def forecast_contributions_from_series(series: pd.Series, periods: int, seasonal: bool = True, m: int = 7, freq: str = "D") -> Dict[str, Any]:
    """Forecast future contributions for `periods` days using auto_arima -> SARIMAX.

    Returns a dict with `forecast` (pd.Series), `conf_int` (pd.DataFrame), and `model` (fit result or None).
    In case of failure it returns a simple mean-based forecast and includes an `error` key.
    """
    if series.empty or periods <= 0:
        idx = pd.date_range(start=pd.Timestamp.today() + pd.Timedelta(days=1), periods=periods, freq="D")
        return {"forecast": pd.Series([0.0] * periods, index=idx), "conf_int": pd.DataFrame(index=idx), "model": None}

    try:
        am = fit_auto_arima(series, seasonal=seasonal, m=m)
        order = am.order
        seasonal_order = am.seasonal_order

        if SARIMAX is None:
            raise RuntimeError("statsmodels is not installed")

        sarimax = SARIMAX(series, order=order, seasonal_order=seasonal_order, enforce_stationarity=False, enforce_invertibility=False)
        res = sarimax.fit(disp=False)
        pred = res.get_forecast(steps=periods)
        mean = pred.predicted_mean
        ci = pred.conf_int()

        # ensure index starts the next period according to requested freq
        offset = to_offset(freq)
        start = series.index.max() + offset
        mean.index = pd.date_range(start=start, periods=periods, freq=freq)
        ci.index = mean.index

        return {"forecast": mean, "conf_int": ci, "model": res}

    except Exception as e:
        # fallback: use recent mean
        recent = series[-30:] if len(series) >= 30 else series
        mean_val = float(np.nanmean(recent)) if len(recent) > 0 else 0.0
        offset = to_offset(freq)
        start = series.index.max() + offset
        idx = pd.date_range(start=start, periods=periods, freq=freq)
        forecast_series = pd.Series([mean_val] * periods, index=idx)
        ci = pd.DataFrame({"lower": forecast_series * 0.9, "upper": forecast_series * 1.1}, index=idx)
        return {"forecast": forecast_series, "conf_int": ci, "model": None, "error": str(e)}


def forecast_contributions_from_weeks(weeks: list, periods: int, seasonal: bool = True, m: int = 7, freq: str = "D") -> Dict[str, Any]:
    """Forecast convenience wrapper that accepts the GitHub weeks payload and optionally a frequency.

    `freq` follows pandas offset aliases (e.g. 'D', 'W', 'M'). When using weekly or monthly
    aggregation, the `periods` argument should represent the number of periods at that freq
    (caller is responsible for converting remaining days -> periods for the chosen freq).
    """
    series = contributions_weeks_to_series(weeks)
    return forecast_contributions_from_series(series, periods=periods, seasonal=seasonal, m=m, freq=freq)
