def calculate_grid_levels(actual_price, min_limit, max_limit, count_of_levels):
    if min_limit >= max_limit:
        raise ValueError("Incorrect values of min_limit and max_limit")

    if actual_price < min_limit or actual_price > max_limit:
        print("Actual price is outside the range (min_limit, max_limit)")

    price_step = (max_limit - min_limit) / (count_of_levels - 1)

    levels = [round(min_limit + i * price_step, 2) for i in range(count_of_levels)]

    buy_levels = [p for p in levels if p < actual_price]
    sell_levels = [p for p in levels if p > actual_price]

    return {
        'levels': levels,
        'buy_levels': buy_levels,
        'sell_levels': sell_levels,
        'price_step': price_step
    }


test_price = 60000.0
grid = calculate_grid_levels(
    test_price,
    55000.0,
    65000.0,
    5
)
print(grid)
