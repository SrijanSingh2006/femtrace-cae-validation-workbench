#include <cmath>
#include <iomanip>
#include <iostream>
#include <sstream>
#include <string>
#include <vector>

struct Finding {
    std::string rule;
    std::string severity;
    double measured;
    double limit;
    std::string unit;
    double gap_pct;
    std::string recommendation;
    std::string status;
};

static void add_check(
    std::vector<Finding>& findings,
    const std::string& rule,
    double measured,
    double limit,
    const std::string& unit,
    const std::string& direction,
    const std::string& recommendation
) {
    double gap_pct = 0.0;
    std::string status = "PASS";
    if (direction == "upper") {
        gap_pct = ((measured - limit) / limit) * 100.0;
        if (measured > limit) status = "FAIL";
        else if (measured >= limit * 0.9) status = "REVIEW";
    } else if (direction == "lower") {
        gap_pct = ((limit - measured) / limit) * 100.0;
        if (measured < limit) status = "FAIL";
        else if (measured < limit * 1.1) status = "REVIEW";
    } else {
        gap_pct = ((measured - limit) / limit) * 100.0;
        const double deviation = std::abs(gap_pct);
        if (deviation > 10.0) status = "FAIL";
        else if (deviation > 5.0) status = "REVIEW";
    }

    if (status != "PASS") {
        findings.push_back({
            rule,
            status == "FAIL" ? "Critical" : "Monitor",
            measured,
            limit,
            unit,
            gap_pct,
            recommendation,
            status
        });
    }
}

int main() {
    std::string line;
    std::cout << std::fixed << std::setprecision(6);
    while (std::getline(std::cin, line)) {
        if (line.empty()) continue;
        std::istringstream input(line);
        double value[10]{};
        for (double& item : value) {
            if (!(input >> item) || !std::isfinite(item)) {
                std::cerr << "Each input row must contain ten finite numeric values.\n";
                return 2;
            }
        }

        const double max_stress = value[0];
        const double allowable_stress = value[1];
        const double yield_strength = value[2];
        const double max_displacement = value[3];
        const double allowable_displacement = value[4];
        const double first_mode = value[5];
        const double minimum_mode = value[6];
        const double minimum_safety_factor = value[7];
        const double mass = value[8];
        const double target_mass = value[9];
        if (allowable_stress <= 0 || yield_strength <= 0 ||
            allowable_displacement <= 0 || minimum_mode <= 0 ||
            minimum_safety_factor <= 0 || target_mass <= 0 ||
            max_stress <= 0 || mass <= 0) {
            std::cerr << "Result and criteria values must be positive where required.\n";
            return 2;
        }

        const double safety_factor = yield_strength / max_stress;
        std::vector<Finding> findings;
        add_check(findings, "Maximum stress", max_stress, allowable_stress, "MPa", "upper",
            "Review material assumptions, load application, local stress concentration and mesh convergence.");
        add_check(findings, "Peak displacement", max_displacement, allowable_displacement, "mm", "upper",
            "Review stiffness, boundary conditions and load path; confirm the displacement limit with the design owner.");
        add_check(findings, "Safety factor", safety_factor, minimum_safety_factor, "x", "lower",
            "Review material properties and the governing load case; confirm the required margin with the design owner.");
        add_check(findings, "First mode frequency", first_mode, minimum_mode, "Hz", "lower",
            "Review stiffness and mass distribution, then compare the mode shape with the intended operating range.");
        add_check(findings, "Mass target", mass, target_mass, "kg", "mass",
            "Review the latest geometry and mass-property extraction against the program target.");

        std::string overall = "PASS";
        for (const Finding& finding : findings) {
            if (finding.status == "FAIL") {
                overall = "FAIL";
                break;
            }
            overall = "REVIEW";
        }
        const double stress_margin = ((allowable_stress - max_stress) / allowable_stress) * 100.0;
        const double displacement_margin =
            ((allowable_displacement - max_displacement) / allowable_displacement) * 100.0;

        std::cout << "{\"status\":\"" << overall
                  << "\",\"safety_factor\":" << safety_factor
                  << ",\"stress_margin_pct\":" << stress_margin
                  << ",\"displacement_margin_pct\":" << displacement_margin
                  << ",\"findings\":[";
        for (std::size_t i = 0; i < findings.size(); ++i) {
            const Finding& item = findings[i];
            if (i) std::cout << ",";
            std::cout << "{\"rule_name\":\"" << item.rule
                      << "\",\"severity\":\"" << item.severity
                      << "\",\"measured_value\":" << item.measured
                      << ",\"limit_value\":" << item.limit
                      << ",\"unit\":\"" << item.unit
                      << "\",\"gap_pct\":" << item.gap_pct
                      << ",\"recommendation\":\"" << item.recommendation
                      << "\",\"status\":\"" << item.status << "\"}";
        }
        std::cout << "]}\n";
    }
    return 0;
}
