"""Plotly charts for the app. Every chart goes through style_chart() so they all look the same."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go

import config

FONT = '"Source Sans", "Source Sans Pro", sans-serif'  # same font Streamlit uses for "sans serif"
TEXT = "#1A1A1A"
DARK_GREY = "#4A4F57"
AXIS = "#B8BDC4"
GRID = "#E6E8EB"
REFERENCE = "#9097A0"   # grey for reference lines: moving averages, Nifty 50
NEGATIVE = "#A23B3B"

# Five restrained colours. Each stock gets a fixed colour from its position in
# config.STOCKS, so it looks the same on every tab. Stocks 6-10 reuse the
# colours with a dashed line, so no two stocks share the same line style.
PALETTE = ["#1F4E79", "#C0692B", "#3B7D4F", "#9B3B3B", "#7D6A2A"]
STOCK_COLOURS = {t: PALETTE[i % len(PALETTE)] for i, t in enumerate(config.STOCKS)}
STOCK_DASH = {t: "solid" if i < len(PALETTE) else "dash" for i, t in enumerate(config.STOCKS)}


def short_name(ticker: str) -> str:
    """'TCS.NS' -> 'TCS', '^NSEI' -> 'Nifty 50'. Used for chart labels."""
    return config.BENCHMARK_NAME if ticker == config.BENCHMARK else ticker.replace(".NS", "")


def style_chart(fig: go.Figure, title: str, x_title: str, y_title: str, height: int = 380) -> go.Figure:
    """Apply the shared look: white background, light horizontal gridlines only, font size 12."""
    fig.update_layout(
        title=dict(text=title, x=0, xanchor="left", font=dict(size=14)),
        font=dict(family=FONT, size=12, color=TEXT),
        paper_bgcolor="white",
        plot_bgcolor="white",
        height=height,
        margin=dict(l=10, r=20, t=48, b=10),
        showlegend=False,
        hoverlabel=dict(bgcolor="white", font=dict(family=FONT, size=12, color=TEXT)),
    )
    # automargin grows the margins so tick labels and axis titles are never cut off
    fig.update_xaxes(title_text=x_title, showgrid=False, zeroline=False, automargin=True,
                     showline=True, linecolor=AXIS, ticks="outside", tickcolor=AXIS,
                     title_standoff=8)
    fig.update_yaxes(title_text=y_title, showgrid=True, gridcolor=GRID, zeroline=False,
                     showline=False, automargin=True, title_standoff=8)
    return fig


def label_line_ends(fig: go.Figure) -> go.Figure:
    """Write each line's name at its last point instead of using a legend."""
    ends = []
    for trace in fig.data:
        points = pd.Series(trace.y, index=trace.x).dropna()
        ends.append([points.index[-1], points.iloc[-1], trace.name, trace.line.color])

    # Push labels apart if their end points are too close to read
    all_y = pd.concat([pd.Series(t.y) for t in fig.data]).dropna()
    min_gap = (all_y.max() - all_y.min()) * 0.05
    ends.sort(key=lambda end: end[1])
    for lower, upper in zip(ends, ends[1:]):
        upper[1] = max(upper[1], lower[1] + min_gap)

    for x, y, name, colour in ends:
        fig.add_annotation(x=x, y=y, text=name, showarrow=False, xanchor="left",
                           xshift=6, font=dict(color=colour, size=12))
    # End the x axis at the last data point so the labels sit right after the lines
    first_x = min(pd.Series(t.x).min() for t in fig.data)
    last_x = max(end[0] for end in ends)
    fig.update_xaxes(range=[first_x, last_x])
    fig.update_layout(margin=dict(r=110))  # room on the right for the labels
    return fig


def price_chart(df: pd.DataFrame, ticker: str) -> go.Figure:
    """Close price with its 30-day and 200-day moving averages."""
    fig = go.Figure()
    lines = [
        ("close", "Close", STOCK_COLOURS[ticker], 1.6, "solid"),
        ("ma_30", "30-day MA", REFERENCE, 1.2, "solid"),
        ("ma_200", "200-day MA", DARK_GREY, 1.3, "dash"),
    ]
    for column, name, colour, width, dash in lines:
        fig.add_trace(go.Scatter(
            x=pd.to_datetime(df["date"]), y=df[column], name=name, mode="lines",
            line=dict(color=colour, width=width, dash=dash),
            hovertemplate=name + ": ₹%{y:,.2f}<extra></extra>",
        ))
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(hoverformat="%d %b %Y")
    style_chart(fig, f"{short_name(ticker)} close price and moving averages", "Date", "Price (₹)")
    return label_line_ends(fig)


def volume_chart(df: pd.DataFrame, ticker: str) -> go.Figure:
    """Monthly average volume as thin vertical bars."""
    fig = go.Figure(go.Bar(
        x=pd.to_datetime(df["month"]), y=df["avg_volume"] / 1e6,
        marker_color=REFERENCE,
        hovertemplate="%{x|%b %Y}: %{y:,.2f} million shares a day<extra></extra>",
    ))
    fig.update_layout(bargap=0.35)
    return style_chart(fig, f"{short_name(ticker)} average daily volume by month",
                       "Month", "Shares a day (million)", height=260)


def cumulative_chart(rebased: pd.DataFrame) -> go.Figure:
    """Growth of 100 rupees for each column. The benchmark is drawn as a thin grey line."""
    fig = go.Figure()
    for ticker in rebased.columns:
        series = rebased[ticker].dropna()
        is_benchmark = ticker == config.BENCHMARK
        fig.add_trace(go.Scatter(
            x=pd.to_datetime(series.index), y=series, name=short_name(ticker), mode="lines",
            line=dict(color=REFERENCE if is_benchmark else STOCK_COLOURS[ticker],
                      width=1.2 if is_benchmark else 1.8,
                      dash="dot" if is_benchmark else STOCK_DASH[ticker]),
            hovertemplate=short_name(ticker) + ": %{y:,.1f}<extra></extra>",
        ))
    fig.add_hline(y=100, line=dict(color=AXIS, width=1))
    fig.update_layout(hovermode="x unified")
    fig.update_xaxes(hoverformat="%d %b %Y")
    style_chart(fig, "Value of 100 invested at the start date", "Date", "Value (start = 100)")
    return label_line_ends(fig)


def correlation_heatmap(corr: pd.DataFrame) -> go.Figure:
    """Correlation matrix with the numbers in the cells. Red below 0, blue above, white at 0."""
    labels = [short_name(t) for t in corr.columns]
    # The diagonal is always 1.00 (a stock with itself), so leave it blank
    values = corr.values.copy()
    np.fill_diagonal(values, np.nan)
    fig = go.Figure(go.Heatmap(
        z=values, x=labels, y=labels,
        zmin=-1, zmax=1, zmid=0,
        colorscale=[[0, NEGATIVE], [0.5, "#FFFFFF"], [1, PALETTE[0]]],
        showscale=False,
        texttemplate="%{z:.2f}",
        xgap=3, ygap=3,
        hoverongaps=False,
        hovertemplate="%{y} and %{x}: %{z:.2f}<extra></extra>",
    ))
    style_chart(fig, "Correlation of daily returns", "", "", height=120 + 60 * len(labels))
    fig.update_xaxes(showline=False, ticks="", side="bottom")
    fig.update_yaxes(showgrid=False, ticks="", autorange="reversed")
    return fig


def bar_chart(values: pd.Series, title: str, x_title: str, highlight: str | None = None) -> go.Figure:
    """Horizontal bars sorted by value, largest at the top.

    Negative bars are red; the bar named in `highlight` is grey (used for the index).
    """
    values = values.sort_values()   # Plotly draws the first bar at the bottom
    colours = [REFERENCE if name == highlight else NEGATIVE if v < 0 else PALETTE[0]
               for name, v in values.items()]
    fig = go.Figure(go.Bar(
        x=values, y=values.index, orientation="h", marker_color=colours,
        texttemplate="%{x:.1f}%", textposition="outside", cliponaxis=False,
        hovertemplate="%{y}: %{x:.2f}%<extra></extra>",
    ))
    fig.update_layout(bargap=0.5)
    style_chart(fig, title, x_title, "", height=60 + 34 * len(values))
    # Leave extra room past the longest bars so the value labels fit
    low, high = min(values.min(), 0), max(values.max(), 0)
    padding = (high - low) * 0.18
    fig.update_xaxes(range=[low - padding if low < 0 else 0, high + padding],
                     showline=False, ticks="", zeroline=True, zerolinecolor=AXIS)
    fig.update_yaxes(showgrid=False)
    return fig
