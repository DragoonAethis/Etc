# /// script
# dependencies = [
#   "bokeh<3.8.0",
# ]
# ///

# This is not financial advice.
# Your bank simulation SHOULD* be more accurate.
# Consult your bank/financial advisor for more info.
# (* unless you ask VeloBank lmao)

# This script simulates mortgage payments over time
# with the following assumptions for the Polish market:
# - Interest accrues daily. Month-to-month variance is simulated.
# - Interest rate is constant across the entire mortgage.
# - You will overpay the mortgage every month, and it's free.
# - Overhead (insurance, extra fees, etc) is configurable.
# You must tweak this script for the exact rules on each
# bank, but the ruleset below matches the ING Bank behavior.

# Edit the variables/code on the bottom, then `uv run mortsim.py`.
# Note: Bokeh 3.8.0 is broken, use 3.7.x or 3.9+:
# https://github.com/bokeh/bokeh/issues/14651

from decimal import Decimal, localcontext
from dataclasses import dataclass
from datetime import date, timedelta

from bokeh import palettes
from bokeh.plotting import figure, show


@dataclass
class MortgageSimulationStep:
    month: int
    capital_left: Decimal
    accrued_interest: Decimal
    effective_interest: Decimal

    capital_part: Decimal
    interest_part: Decimal
    overhead_part: Decimal


class Mortgage:
    initial_capital: Decimal
    capital_left: Decimal
    month: int

    const_part: Decimal
    variable_installments: bool
    installment_overhead: callable

    interest_pct: Decimal
    interest_pct: Decimal
    total_interest_accrued: Decimal

    def __init__(
            self,
            capital: Decimal,
            const_part: Decimal,
            variable_installments: bool,
            interest: Decimal,
            installment_overhead: callable,
    ):
        self.initial_capital = capital
        self.capital_left = capital
        self.month = 0

        self.const_part = const_part
        self.variable_installments = variable_installments
        self.installment_overhead = installment_overhead

        self.interest_pct = interest
        self.total_interest_accrued = Decimal("0.0")

    def step(self, delta_days = int):
        step: MortgageSimulationStep
        installment_interest = (self.capital_left * self.interest_pct) / Decimal(365) * Decimal(delta_days)

        if self.variable_installments:
            # Decreasing installments, constant capital, decreasing interest
            installment_capital = min(self.const_part, self.capital_left)
        else:
            # Constant installments, decreasing interest, increasing capital
            expected_capital = self.const_part - installment_interest
            installment_capital = min(expected_capital, self.capital_left)
            if installment_capital < 0:
                raise ValueError(f"Simulation step impossible - interest + overhead value > installment value of {self.const_part}")

        overhead = self.installment_overhead(self, self.capital_left)

        self.month += 1
        self.capital_left -= installment_capital
        self.total_interest_accrued += installment_interest

        step = MortgageSimulationStep(
            month=self.month,
            capital_left=self.capital_left,
            accrued_interest=self.total_interest_accrued,
            effective_interest=self.interest_pct,
            interest_part=installment_interest,
            capital_part=installment_capital,
            overhead_part=overhead,
        )

        return step


def run_simulation(mortgage: Mortgage, monthly_overpayments: Decimal, pay_date: date = None):
    months = []
    overhead, capital, interest, overpayments = [], [], [], []
    parts = ["overhead", "capital", "interest", "overpayments"]

    if not pay_date:
        pay_date = date.today()

    if pay_date.day > 28:
        raise ValueError("Pay date must be valid for all months (no later than on 28th)")

    initial_pay_date = pay_date
    initial_interest_part = None

    while mortgage.capital_left > Decimal("0.01"):
        prev_pay_date = pay_date
        if prev_pay_date.month == 12:
            pay_date = prev_pay_date.replace(year=pay_date.year + 1, month=1)
        else:
            pay_date = prev_pay_date.replace(month=pay_date.month + 1)

        delta_days = abs((prev_pay_date - pay_date).days)

        step = mortgage.step(delta_days=delta_days)
        months.append(pay_date)
        overhead.append(step.overhead_part)
        capital.append(step.capital_part)
        interest.append(step.interest_part)

        if initial_interest_part is None:
            initial_interest_part = step.interest_part

        overpayment = min(monthly_overpayments, mortgage.capital_left)

        # OVERPAYMENTS COST YOU? DEFINE HOW HERE!
        # Add the cost to the overhead for completeness.

        # Example for a 3% fee for the first 3 years:
        #if step.month <= 36:
        #    overhead[-1] += overpayment * Decimal("0.03")
        #    overpayment *= Decimal("0.97")

        mortgage.capital_left -= overpayment
        overpayments.append(overpayment)

        print(f"[MONTH {step.month:3d}] Capital Left: {step.capital_left:10.02f} - Total Interest: {step.accrued_interest:10.02f}")

    print(f"Finished in {step.month} months from {initial_pay_date} to {pay_date}.")

    print("####### TOTALS:")
    print(f"-      Capital: {sum(capital):10.02f}")
    print(f"-     Interest: {sum(interest):10.02f}")
    print(f"-     Overhead: {sum(overhead):10.02f}")
    print(f"- Overpayments: {sum(overpayments):10.02f}")

    month_labels = [f"{x.year}-{x.month:02}" for x in months]
    p = figure(
        title="Mortgage simulation",
        x_range=month_labels,
        x_axis_label="Month",
        y_axis_label="Costs",
        height=1000,
        width=1800,
        #toolbar_location=None,
        tools="hover,pan,wheel_zoom,box_zoom,save,reset,help",
        tooltips="$name @months: @$name{0.00}",
    )

    data_source = {
        "months": month_labels,
        "overhead": [float(x) for x in overhead],
        "interest": [float(x) for x in interest],
        "capital": [float(x) for x in capital],
        "overpayments": [float(x) for x in overpayments],
    }

    p.vbar_stack(
        parts,
        x='months',
        width=0.9,
        color=palettes.Vibrant4,
        source=data_source,
        legend_label=parts,
    )

    p.y_range.start = 0
    p.x_range.range_padding = 0.1
    p.xaxis.major_label_orientation = "vertical"
    p.xgrid.grid_line_color = None
    p.axis.minor_tick_line_color = None
    p.outline_line_color = None
    p.legend.location = "top_right"
    p.legend.orientation = "vertical"

    show(p)


def calc_overhead(mortgage: Mortgage, remaining_capital: Decimal):
    # Insurance, etc rules go here:
    return Decimal("0.00035") * remaining_capital


def main():
    capital = Decimal("500000")
    interest = Decimal("0.0632")
    overpayment = Decimal("3000")  # Can be 0 if you want.

    # Day 0 to start the simulation. This is the first day
    # interest starts being accrued. Can be date.today(), or...
    pay_date = date(year=2025, month=9, day=20)

    # VARIABLE INSTALLMENTS
    #variable = True
    #mortgage_months = 12 * 30
    #const_part = Decimal(capital / mortgage_months)

    # CONSTANT INSTALLMENTS - mortgage months are simulated
    variable = False
    const_part = Decimal("3000.00")  # Example total installment value

    mortgage = Mortgage(
        capital=capital,
        const_part=const_part,
        variable_installments=variable,
        interest=interest,
        installment_overhead=calc_overhead,
    )

    run_simulation(
        mortgage,
        monthly_overpayments=overpayment,
        pay_date=pay_date,
    )


if __name__ == "__main__":
    with localcontext(prec=32) as ctx:
        main()
