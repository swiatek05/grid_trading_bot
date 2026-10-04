import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from grid_strategy import calculate_grid_levels

def test_calculate_grid_levels_basic():
    #Tests basic mesh generation with correct parameters.
    actual_price = 60000.0
    min_limit = 50000.0
    max_limit = 70000.0
    count_of_levels = 5

    result = calculate_grid_levels(actual_price, min_limit, max_limit, count_of_levels)

    assert len(result['levels']) == 5
    assert result['levels'][0] == 50000.0
    assert result['levels'][-1] == 70000.0
    assert len(result['buy_levels']) == 3
    assert len(result['sell_levels']) == 2

def test_calculate_grid_levels_invalid_limits():

    #test checking  if parameters are correct
    with pytest.raises(ValueError):
        calculate_grid_levels(60000.0, 70000.0, 50000.0, 5)

def test_calculate_grid_levels_price_outside_range():
    #The test checks whether the levels are distributed correctly.

    actual_price = 40000.0
    result = calculate_grid_levels(actual_price, 50000.0, 70000.0, 5)
    
    assert len(result['levels']) == 5
    assert len(result['buy_levels']) == 0 #lack of buy
    assert len(result['sell_levels']) == 5 # all of orders are type of SELL
