"""
test_analysis.py - Test unitari per src/analysis/*.py

Coprono solo le funzioni pure (nessun accesso a database): i test lavorano
su Series/DataFrame/array sintetici costruiti a mano, non sui dati reali.
"""

import numpy as np
import pandas as pd
import pytest

from src.analysis.trend_analysis import mann_kendall_trend, linear_trend
from src.analysis.spatial_analysis import (
    haversine_km,
    build_inverse_distance_weights,
    morans_i,
    climate_clustering,
)
from src.analysis.heatwave_stats import summary_by_municipality, frequency_by_year
from src.machine_learning.climate_clustering import build_pipeline, label_mapping


class TestMannKendallTrend:
    def test_detects_increasing_trend(self):
        years = np.arange(2000, 2026)
        noise = np.random.RandomState(0).normal(0, 0.1, len(years))
        values = pd.Series(0.05 * (years - 2000) + 10 + noise)

        result = mann_kendall_trend(values)

        assert result['mk_trend'] == 'increasing'
        assert result['mk_p_value'] < 0.05

    def test_no_trend_for_flat_noisy_series(self):
        values = pd.Series(np.random.RandomState(1).normal(10, 0.5, 26))

        result = mann_kendall_trend(values)

        assert result['mk_trend'] == 'no trend'


class TestLinearTrend:
    def test_recovers_known_slope(self):
        years = pd.Series(np.arange(2000, 2026))
        true_slope = 0.05
        values = years * true_slope + 10.0

        result = linear_trend(years, values)

        assert result['lr_slope_per_year'] == pytest.approx(true_slope, abs=1e-6)
        assert result['lr_slope_per_decade'] == pytest.approx(true_slope * 10, abs=1e-6)
        assert result['lr_r_squared'] == pytest.approx(1.0, abs=1e-6)


class TestHaversineKm:
    def test_zero_distance_for_same_point(self):
        assert haversine_km(7.68, 45.07, 7.68, 45.07) == pytest.approx(0, abs=1e-9)

    def test_known_distance_torino_milano(self):
        # Torino (7.68, 45.07) - Milano (9.19, 45.46), distanza reale ~126 km
        d = haversine_km(7.68, 45.07, 9.19, 45.46)
        assert 100 < d < 150


class TestInverseDistanceWeights:
    def _sample_df(self):
        return pd.DataFrame({'lon': [7.68, 8.19, 8.62], 'lat': [45.07, 44.90, 45.44]})

    def test_rows_sum_to_one(self):
        w = build_inverse_distance_weights(self._sample_df())
        assert np.allclose(w.sum(axis=1), 1.0)

    def test_diagonal_is_zero(self):
        w = build_inverse_distance_weights(self._sample_df())
        assert np.allclose(np.diag(w), 0.0)


class TestMoransI:
    def test_positive_for_spatially_clustered_values(self):
        # Due gruppi di punti geograficamente lontani, con valori simili
        # all'interno di ciascun gruppo e molto diversi tra i due gruppi:
        # autocorrelazione spaziale positiva attesa, forte.
        df = pd.DataFrame({
            'lon': [0.0, 0.01, 0.02, 10.0, 10.01, 10.02],
            'lat': [0.0, 0.01, 0.02, 10.0, 10.01, 10.02],
        })
        values = np.array([1.0, 1.1, 0.9, 20.0, 20.1, 19.9])
        w = build_inverse_distance_weights(df)

        result = morans_i(values, w)

        assert result > 0.5


class TestClimateClustering:
    def test_separates_two_clearly_distinct_groups(self):
        df = pd.DataFrame({
            'temp_mean_avg': [5.0, 5.2, 4.8, 20.0, 20.3, 19.7],
            'days_gt_30c_avg': [0.0, 1.0, 0.0, 60.0, 58.0, 62.0],
            'days_gt_35c_avg': [0.0, 0.0, 0.0, 20.0, 19.0, 21.0],
        })

        labels = climate_clustering(df, k=2)

        assert labels.iloc[0] == labels.iloc[1] == labels.iloc[2]
        assert labels.iloc[3] == labels.iloc[4] == labels.iloc[5]
        assert labels.iloc[0] != labels.iloc[3]

    def test_matches_ml_pipeline_with_ordered_labels(self):
        rng = np.random.RandomState(7)
        centers = np.array([[8.0, 2.0, 0.0], [13.0, 20.0, 3.0], [17.0, 50.0, 12.0]])
        values = np.vstack([c + rng.normal(0, [0.5, 2.0, 1.0], (10, 3)) for c in centers])
        df = pd.DataFrame(
            values,
            columns=['temp_mean_avg', 'days_gt_30c_avg', 'days_gt_35c_avg'],
            index=pd.RangeIndex(100, 130),
        )

        labels = climate_clustering(df, k=3)

        raw = build_pipeline(3).fit_predict(df)
        expected = pd.Series(raw, index=df.index).map(label_mapping(df, raw))
        assert labels.name == 'climate_cluster'
        assert labels.index.equals(df.index)
        assert labels.tolist() == expected.tolist()
        mean_temp = df['temp_mean_avg'].groupby(labels).mean()
        assert mean_temp.is_monotonic_increasing


class TestHeatwaveStatsSummary:
    def test_summary_by_municipality_counts_and_averages(self):
        df = pd.DataFrame({
            'municipality_name': ['Torino', 'Torino', 'Asti'],
            'duration_days': [3, 5, 4],
            'intensity_index': [10.0, 20.0, 15.0],
            'max_temp': [36.0, 38.0, 37.0],
        })

        summary = summary_by_municipality(df)
        torino = summary[summary['municipality_name'] == 'Torino'].iloc[0]

        assert torino['n_heatwaves'] == 2
        assert torino['avg_duration_days'] == pytest.approx(4.0)
        assert torino['max_duration_days'] == 5

    def test_frequency_by_year_includes_years_with_zero_events(self):
        df = pd.DataFrame({
            'start_date': ['2003-08-01', '2003-08-10', '2005-07-15'],
            'duration_days': [3, 4, 5],
            'intensity_index': [2.5, 3.0, 4.0],
        })

        result = frequency_by_year(df)

        assert result['year'].tolist() == [2003, 2004, 2005]
        assert result.loc[result['year'] == 2003, 'n_heatwaves'].iloc[0] == 2
        assert result.loc[result['year'] == 2004, 'n_heatwaves'].iloc[0] == 0
