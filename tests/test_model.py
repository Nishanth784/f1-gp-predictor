import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
import pandas as pd

from model import align_features_to_model, train_and_evaluate


def test_align_features_to_model_adds_missing_cols():
	X = pd.DataFrame({"a": [1.0, 2.0]})
	expected = ["a", "b"]
	aligned = align_features_to_model(X, expected)
	assert list(aligned.columns) == expected
	assert np.allclose(aligned["b"], 0.0)


def test_train_and_evaluate_runs():
	# Small synthetic dataset
	X = pd.DataFrame({
		"f1": np.random.randn(100),
		"f2": np.random.randn(100),
		"f3": np.random.randn(100),
	})
	y = 2 * X["f1"] - 0.5 * X["f2"] + np.random.randn(100) * 0.1
	metrics = train_and_evaluate(X, y)
	assert metrics, "Expected non-empty metrics dict"
