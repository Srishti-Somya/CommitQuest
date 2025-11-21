import streamlit as st
from streamlit import session_state as sst
from datetime import datetime, timedelta
from utils.fetch_github_data import fetch_data_for_duration, fetch_user_data
from utils.process_github_data import analyze_contributions, process_user_data
from utils.util import predict_days_to_milestone, get_milestone_dates, format_date_ddmmyyyy
from utils.arima_predictor import forecast_contributions_from_weeks
from utils.streamlit_ui import base_ui
from utils.arima_predictor import contributions_weeks_to_series
import plotly.graph_objects as go

def main():
    base_ui()

    if sst.username and sst.token and sst.button_pressed:                
        # Fetch data
        user_data = fetch_user_data(sst.username, sst.token)
        user_stats = process_user_data(user_data)
        created_at = datetime.strptime(user_stats.get("created_at"), "%Y-%m-%dT%H:%M:%SZ")
        created_at = created_at.strftime("%Y-%m-%d")

        today = datetime.now().strftime("%Y-%m-%d")
        current_year = datetime.now().year
        current_jan1st = datetime(current_year, 1, 1).strftime("%Y-%m-%d")
        last_jan1st = datetime(current_year-1, 1, 1).strftime("%Y-%m-%d")
        last_dec31st = datetime(current_year-1, 12, 31).strftime("%Y-%m-%d")

        # ------------- Last Year Contributions
        last_year_data_present = True
        from_date= last_jan1st# Date comes before Jan 1st. We use Jan 1st as starting date
        to_date= last_dec31st

        # Date comes between Jan 1st and Dec 31st. We use join date as start date
        if last_jan1st < created_at < last_dec31st: 
            from_date= created_at
        # Date comes after Dec 31st. Unable to calculate rate for last year
        elif created_at >= last_dec31st:
            last_year_data_present = False
        
            
        # If last year data is present
        if last_year_data_present:
            year_data = fetch_data_for_duration(
                sst.username, 
                sst.token,
                from_date= from_date,
                to_date= to_date
            )
            # Analyze only when data present
            whole_year_stats = analyze_contributions(year_data)

            # --- Get required stats ---
            contribution_rate_ly = whole_year_stats.get('contribution_rate', 0)
            # active_days_ly = whole_year_stats.get('active_days', 0)
        else:
            contribution_rate_ly = 0


        # -------------- Current Year Data
        from_date= created_at
        # Fetching current year data
        if current_jan1st >= created_at: # If joined before Jan 1st
            from_date= current_jan1st
        current_year_data = fetch_data_for_duration(
            sst.username, 
            sst.token,
            from_date= from_date,
            to_date= today
            )
        
        # Process current year data
        current_year_stats = analyze_contributions(current_year_data)
        
        # --- Current year stats ---
        total_contributions = current_year_stats.get('total_contributions', 0)
        total_days = current_year_stats.get('total_days', 0)
        contribution_rate = current_year_stats.get('contribution_rate', 0)
        active_days = current_year_stats.get('active_days', 0)

        # --- Future Predictions ---
        if contribution_rate_ly == 0:
            growth_rate = 0
        else:
            growth_rate = ((contribution_rate - contribution_rate_ly) / contribution_rate_ly) * 100  # Growth in %

        # if active_days_ly == 0:
        #     active_days_growth = 0
        # else:
        #     active_days_growth = ((active_days - active_days_ly) / active_days_ly) * 100  # Growth in %

        remaining_days = max(0, 365 - total_days)

        # Original (average-based) predictions — keep these as the default values shown to users.
        avg_predicted_future_contributions = contribution_rate * remaining_days
        avg_predicted_future_active_days = (active_days / total_days) * remaining_days if total_days > 0 else 0

        # Ensure session_state keys for ARIMA results exist
        if "arima_results" not in sst:
            sst.arima_results = None
        if "arima_error" not in sst:
            sst.arima_error = None


        with st.container():
            # --- Predictions & Trends ---
            st.markdown("#### :material/timeline: **Predictions & Trends**")

            col1, col2, col3 = st.columns(3)

            col1.metric(
                label="Contribution Rate Growth",
                value=f"{growth_rate:.2f}%",
                delta="+Increasing" if growth_rate > 0 else "-Decreasing",
                help="Growth in contribution rate compared to last year",
                border=True
            )

            # Choose which prediction to display: default to average-based, override if ARIMA results exist in session state
            display_predicted_future_contributions = avg_predicted_future_contributions
            display_predicted_future_active_days = avg_predicted_future_active_days
            if sst.arima_results:
                try:
                    display_predicted_future_contributions = sst.arima_results.get("predicted_future_contributions", display_predicted_future_contributions)
                    display_predicted_future_active_days = sst.arima_results.get("predicted_future_active_days", display_predicted_future_active_days)
                except Exception:
                    pass

            col2.metric(
                label="Predicted Contributions This Year",
                value=f"{display_predicted_future_contributions + total_contributions:.0f} commits",
                delta=f"{'-' if display_predicted_future_contributions<=0 else '+'}{display_predicted_future_contributions:.0f} commits",
                help="Total predicted commits this year, if user continues to contribute at the same rate",
                border=True
            )

            col3.metric(
                label="Predicted Active Days This Year",
                value=f"{display_predicted_future_active_days + active_days:.0f} days",
                delta=f"{'-' if display_predicted_future_active_days <= 0 else '+'} {display_predicted_future_active_days:.0f} days",
                delta_color="off" if display_predicted_future_active_days <= 0 else "normal",
                help="Total predicted active days this year, if user continues to contribute at the same rate",
                border=True
            )

            # If ARIMA results exist, show a small summary block so users can compare methods
            if sst.arima_results:
                with st.expander("ARIMA Prediction Details", expanded=False):
                    st.write(f"Predicted future contributions (ARIMA): {sst.arima_results['predicted_future_contributions']:.2f}")
                    st.write(f"Predicted future active days (ARIMA): {sst.arima_results['predicted_future_active_days']}")
                    if sst.arima_error:
                        st.warning(f"Note: ARIMA error: {sst.arima_error}")

        # Milestone goals
        milestones = [100, 500, 1000, 2000, 5000, 10000]
        with st.container():
            st.markdown("#### :material/done_all: Milestones Estimations")
            if sst.user_token:
            
                # User's current contributions
                current_contributions = current_year_stats.get("total_contributions", 0)
                if current_contributions == 0:
                    st.error("No contributions found for the current year.")
                    st.stop()
                # Calculate days required for each milestone
                milestone_predictions = {
                    milestone: predict_days_to_milestone(current_contributions, milestone, contribution_rate)
                    for milestone in milestones
                }

                contributions = current_year_data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]

                milestone_dates = get_milestone_dates(milestones, contributions, total_contributions, contribution_rate)


                # Display Milestones
            

                col1, col2 = st.columns(2, border=True)

                for i, (milestone, days) in enumerate(milestone_predictions.items()):
                    col = col1 if i % 2 == 0 else col2  # Alternate between columns
                    if total_contributions >= milestone:
                        # Unlocked Milestone
                        status = milestone_dates.get(milestone, 'Not Achieveable')
                        date = ''
                        if status != 'Not Achieveable':
                            date = format_date_ddmmyyyy(status)
                        col.metric(
                            label=f"✅ Achieved Milestone: {milestone} commits",
                            value=f"{date}" if date else "Achieved",
                            delta="Achieved",
                        )
                        col.progress(100, text=f"{total_contributions}/{milestone}")
                        col.divider()
                        

                    
                    else:
                        progress = min(100, (total_contributions / milestone) * 100)
                        # Locked Milestone with Progress Bar
                        status = milestone_dates.get(milestone, 'Not Achieveable')
                        date = ''
                        if status != 'Not Achieveable':
                            date = format_date_ddmmyyyy(status)
                        col.metric(
                            label=f"Estimated days to {milestone} commits",
                            value=f"{date}" if date else "Not achievable",
                            delta=f"{days:.0f} days" if days != float('inf') else "Not achievable"
                        )

                        if progress > 0:
                            col.progress(progress / 100, text=f"{total_contributions}/{milestone}")
                            col.divider()
            else:
                st.info("Create GitHub Access Token to view these stats")

        # --- Controls to run and reveal ARIMA Predictions section ---
        # Place the explicit Run button just above the Show ARIMA button as requested
        if st.button("Run ARIMA Prediction"):
            try:
                weeks = current_year_data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
                arima_res = forecast_contributions_from_weeks(weeks, periods=remaining_days, seasonal=True, m=7)
                forecast = arima_res.get("forecast")
                if forecast is not None and len(forecast) > 0:
                    arima_predicted_future_contributions = float(forecast.sum())
                    arima_predicted_future_active_days = int((forecast > 0).sum())
                else:
                    arima_predicted_future_contributions = avg_predicted_future_contributions
                    arima_predicted_future_active_days = avg_predicted_future_active_days

                if forecast is not None and len(forecast) > 0:
                    ci = arima_res.get("conf_int")
                    lower = list(ci.iloc[:, 0].astype(float)) if ci is not None and not ci.empty else []
                    upper = list(ci.iloc[:, 1].astype(float)) if ci is not None and not ci.empty else []
                    sst.arima_results = {
                        "predicted_future_contributions": arima_predicted_future_contributions,
                        "predicted_future_active_days": arima_predicted_future_active_days,
                        "forecast_values": list(map(float, forecast.values)),
                        "forecast_dates": [d.strftime("%Y-%m-%d") for d in forecast.index],
                        "conf_int_lower": lower,
                        "conf_int_upper": upper,
                    }
                else:
                    sst.arima_results = {
                        "predicted_future_contributions": arima_predicted_future_contributions,
                        "predicted_future_active_days": arima_predicted_future_active_days,
                        "forecast_values": [],
                        "forecast_dates": [],
                        "conf_int_lower": [],
                        "conf_int_upper": [],
                    }
                sst.arima_error = None
                st.success("ARIMA prediction completed and applied.")
            except Exception as e:
                sst.arima_results = None
                sst.arima_error = str(e)
                st.error(f"ARIMA prediction failed: {e}")

        if st.button("Show ARIMA Predictions"):
            sst.show_arima_section = True

        if getattr(sst, "show_arima_section", False):
            # Prepare ARIMA results if not present
            try:
                if not sst.arima_results:
                    weeks = current_year_data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
                    arima_res = forecast_contributions_from_weeks(weeks, periods=remaining_days, seasonal=True, m=7)
                    forecast = arima_res.get("forecast")
                    if forecast is not None and len(forecast) > 0:
                        ci = arima_res.get("conf_int")
                        lower = list(ci.iloc[:, 0].astype(float)) if ci is not None and not ci.empty else []
                        upper = list(ci.iloc[:, 1].astype(float)) if ci is not None and not ci.empty else []
                        sst.arima_results = {
                            "predicted_future_contributions": float(forecast.sum()),
                            "predicted_future_active_days": int((forecast > 0).sum()),
                            "forecast_values": list(map(float, forecast.values)),
                            "forecast_dates": [d.strftime("%Y-%m-%d") for d in forecast.index],
                            "conf_int_lower": lower,
                            "conf_int_upper": upper,
                        }
                    else:
                        sst.arima_results = {
                            "predicted_future_contributions": avg_predicted_future_contributions,
                            "predicted_future_active_days": avg_predicted_future_active_days,
                            "forecast_values": [],
                            "forecast_dates": [],
                            "conf_int_lower": [],
                            "conf_int_upper": [],
                        }
            except Exception as e:
                sst.arima_results = None
                sst.arima_error = str(e)

            # --- ARIMA Predictions Section ---
            with st.container():
                st.markdown("#### :bar_chart: ARIMA / SARIMA Predictions")

                # ARIMA metrics (fallback to averages if absent)
                arima_fc = sst.arima_results or {}
                arima_future_contribs = arima_fc.get("predicted_future_contributions", avg_predicted_future_contributions)
                arima_future_active_days = arima_fc.get("predicted_future_active_days", avg_predicted_future_active_days)

                # Compute ARIMA contribution rate for remaining days
                arima_rate = (arima_future_contribs / remaining_days) if remaining_days > 0 else 0

                # Growth compared to last year
                if contribution_rate_ly == 0:
                    arima_growth = 0
                else:
                    arima_growth = ((arima_rate - contribution_rate_ly) / contribution_rate_ly) * 100

                c1, c2, c3 = st.columns(3)
                c1.metric(label="Contribution Rate Growth (ARIMA)", value=f"{arima_growth:.2f}%", delta="+Increasing" if arima_growth>0 else "-Decreasing")
                c2.metric(label="Predicted Contributions This Year (ARIMA)", value=f"{(arima_future_contribs + total_contributions):.0f} commits", delta=f"{'+' if arima_future_contribs>0 else '-'}{arima_future_contribs:.0f} commits")
                c3.metric(label="Predicted Active Days This Year (ARIMA)", value=f"{(arima_future_active_days + active_days):.0f} days", delta=f"{'+' if arima_future_active_days>0 else '-'}{arima_future_active_days:.0f} days")

                # Milestone estimates using ARIMA forecast
                st.markdown("**Estimated milestone dates (ARIMA)**")
                milestones_to_check = [2000, 5000, 10000]

                def find_milestone_date_from_forecast(total_current, forecast_values, forecast_dates, milestone):
                    remaining_needed = milestone - total_current
                    if remaining_needed <= 0:
                        return datetime.now().strftime("%Y-%m-%d")
                    cum = 0.0
                    for val, date in zip(forecast_values, forecast_dates):
                        cum += val
                        if cum >= remaining_needed:
                            return date
                    return None

                # Display milestone dates
                for m in milestones_to_check:
                    date = None
                    if sst.arima_results and sst.arima_results.get("forecast_values"):
                        date = find_milestone_date_from_forecast(total_contributions, sst.arima_results.get("forecast_values", []), sst.arima_results.get("forecast_dates", []), m)
                    if date:
                        st.write(f"Milestone {m}: estimated on {date} (ARIMA)")
                    else:
                        # fallback to average days
                        days_needed = predict_days_to_milestone(total_contributions, m, contribution_rate)
                        if days_needed == float('inf'):
                            st.write(f"Milestone {m}: Not achievable with current average rate")
                        else:
                            eta = datetime.now() + timedelta(days=days_needed)
                            st.write(f"Milestone {m}: estimated on {eta.strftime('%Y-%m-%d')} (Average, {days_needed:.0f} days)")

                # Visualization: historical series + ARIMA forecast
                try:
                    weeks = current_year_data["data"]["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]
                    hist_series = contributions_weeks_to_series(weeks)
                    fc_vals = sst.arima_results.get("forecast_values", []) if sst.arima_results else []
                    fc_dates = sst.arima_results.get("forecast_dates", []) if sst.arima_results else []
                    lower = sst.arima_results.get("conf_int_lower", []) if sst.arima_results else []
                    upper = sst.arima_results.get("conf_int_upper", []) if sst.arima_results else []

                    fig = go.Figure()
                    if not hist_series.empty:
                        fig.add_trace(go.Scatter(x=hist_series.index, y=hist_series.values, mode='lines', name='History', line=dict(color='white')))
                    if fc_vals and fc_dates:
                        fig.add_trace(go.Scatter(x=fc_dates, y=fc_vals, mode='lines+markers', name='ARIMA Forecast', line=dict(color='yellow')))
                        if lower and upper and len(lower)==len(fc_vals) and len(upper)==len(fc_vals):
                            fig.add_trace(go.Scatter(x=fc_dates+fc_dates[::-1], y=upper+lower[::-1], fill='toself', fillcolor='rgba(255,255,0,0.1)', line=dict(color='rgba(255,255,0,0)'), showlegend=False))
                    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='white', height=350)
                    st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
                except Exception:
                    st.info("ARIMA visualization unavailable")

                # Custom target prediction in ARIMA section
                with st.container():
                    st.markdown("#### :dart: Custom Target Prediction (ARIMA)")
                    tcol_a, tcol_b = st.columns([3,1])
                    target_commits_arima = tcol_a.number_input("Enter target total commits (absolute number):", min_value=1, value=int(total_contributions + 150), step=1, key='arima_target')
                    if tcol_b.button("Predict Target Date (ARIMA)"):
                        predicted_date = None
                        if sst.arima_results and sst.arima_results.get("forecast_values"):
                            predicted_date = find_milestone_date_from_forecast(total_contributions, sst.arima_results.get("forecast_values", []), sst.arima_results.get("forecast_dates", []), target_commits_arima)
                        if predicted_date:
                            st.success(f"Estimated date to reach {target_commits_arima} commits (ARIMA): {predicted_date}")
                        else:
                            days_needed = predict_days_to_milestone(total_contributions, target_commits_arima, contribution_rate)
                            if days_needed == float('inf'):
                                st.error("Cannot estimate date: contribution rate is zero.")
                            else:
                                eta = datetime.now() + timedelta(days=days_needed)
                                st.info(f"Estimated date to reach {target_commits_arima} commits (Average): {eta.strftime('%Y-%m-%d')} ({days_needed:.0f} days)")



    else:
        st.info("ℹ️ ***Enter your GitHub username in the sidebar to see your stats.***")

if __name__ == "__main__":
    main()