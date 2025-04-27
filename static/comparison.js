// Pension Agreement Comparison Module
// Isolated from calculator.js for fault tolerance
const PensionComparison = (function() {
    // Cache DOM elements
    const compareBtn = document.getElementById('compare-btn');
    const resetBtn = document.getElementById('reset-btn');
    const errorContainer = document.getElementById('comparison-error');
    const resultsContainer = document.getElementById('comparison-results');
    
    // Agreement and scenario selectors
    const agreement1Select = document.getElementById('agreement1');
    const scenario1Select = document.getElementById('scenario1');
    const agreement2Select = document.getElementById('agreement2');
    const scenario2Select = document.getElementById('scenario2');
    
    // Common parameter inputs
    const ageInput = document.getElementById('age');
    const salaryInput = document.getElementById('salary');
    const retirementAgeInput = document.getElementById('retirement_age');
    const growthInput = document.getElementById('growth');
    const salaryExchangeInput = document.getElementById('salary_exchange');
    
    // Parameters for different agreements (matching the backend parameters)
    const pensionParameters = {
        "PA16": {
            "scenarios": {
                "Avd1": {
                    "type": "premiebestämd",
                    "contribution_rate_below_cap": 0.045,
                    "contribution_rate_above_cap": 0.30,
                    "income_cap_base_amount": 7.5,
                    "income_base_amount": 74000,
                    "admin_fee_percentage": 0.003,
                    "default_return_rate": 0.019, 
                    "default_retirement_age": 65
                },
                "Avd2": {
                    "type": "förmånsbestämd",
                    "contribution_rate_below_cap": null,
                    "contribution_rate_above_cap": null,
                    "income_cap_base_amount": 7.5,
                    "income_base_amount": 74000,
                    "admin_fee_percentage": 0.003,
                    "default_return_rate": 0.019, 
                    "default_retirement_age": 65,
                    "defined_benefit_levels": [
                        { "years": "<=30", "percent": 0.10 },
                        { "years": ">30", "percent": 0.65 }
                    ],
                    "itpk_contribution_rate": 0.02
                }
            }
        },
        "SKR2023": {
            "scenarios": {
                "Standard": {
                    "type": "premiebestämd",
                    "contribution_rate_below_cap": 0.045,
                    "contribution_rate_above_cap": 0.065,
                    "income_cap_base_amount": 7.5,
                    "income_base_amount": 74000,
                    "admin_fee_percentage": 0.002,
                    "default_return_rate": 0.019,
                    "default_retirement_age": 65
                }
            }
        }
    };
    
    // Initialize the comparison module
    function init() {
        // Add event listeners
        compareBtn.addEventListener('click', compareAgreements);
        resetBtn.addEventListener('click', resetComparison);
        
        // Setup agreement change listeners
        agreement1Select.addEventListener('change', function() {
            updateScenarioOptions(agreement1Select, scenario1Select);
        });
        
        agreement2Select.addEventListener('change', function() {
            updateScenarioOptions(agreement2Select, scenario2Select);
        });
        
        // Initialize scenario options
        updateScenarioOptions(agreement1Select, scenario1Select);
        updateScenarioOptions(agreement2Select, scenario2Select);
    }
    
    // Update scenario options based on selected agreement
    function updateScenarioOptions(agreementSelect, scenarioSelect) {
        const agreement = agreementSelect.value;
        
        // Clear existing options
        scenarioSelect.innerHTML = '';
        
        // Get scenarios for selected agreement
        const scenarios = pensionParameters[agreement].scenarios;
        
        // Add options for each scenario
        for (const [key, value] of Object.entries(scenarios)) {
            const option = document.createElement('option');
            option.value = key;
            
            // Use friendly names for scenarios
            switch (key) {
                case 'Avd1':
                    option.textContent = 'Avdelning 1';
                    break;
                case 'Avd2':
                    option.textContent = 'Avdelning 2';
                    break;
                case 'Standard':
                    option.textContent = 'Standard';
                    break;
                default:
                    option.textContent = key;
            }
            
            scenarioSelect.appendChild(option);
        }
    }
    
    // Reset the comparison form to defaults
    function resetComparison() {
        // Reset agreement and scenario selections
        agreement1Select.value = 'PA16';
        updateScenarioOptions(agreement1Select, scenario1Select);
        scenario1Select.value = 'Avd1';
        
        agreement2Select.value = 'SKR2023';
        updateScenarioOptions(agreement2Select, scenario2Select);
        scenario2Select.value = 'Standard';
        
        // Reset common parameters
        ageInput.value = 40;
        salaryInput.value = 35000;
        retirementAgeInput.value = 65;
        growthInput.value = 1.9;
        salaryExchangeInput.value = 0;
        
        // Hide results and errors
        errorContainer.style.display = 'none';
        resultsContainer.style.display = 'none';
    }
    
    // Extract user input values
    function getFormValues() {
        return {
            agreement1: agreement1Select.value,
            scenario1: scenario1Select.value,
            agreement2: agreement2Select.value,
            scenario2: scenario2Select.value,
            age: parseInt(ageInput.value, 10),
            monthly_salary: parseInt(salaryInput.value, 10),
            retirement_age: parseInt(retirementAgeInput.value, 10),
            growth: parseFloat(growthInput.value) / 100,
            salary_exchange: parseInt(salaryExchangeInput.value, 10) || 0
        };
    }
    
    // Validate form inputs
    function validateInputs(formData) {
        if (isNaN(formData.age) || formData.age < 18 || formData.age > 70) {
            return 'Åldern måste vara mellan 18 och 70 år.';
        }
        
        if (isNaN(formData.monthly_salary) || formData.monthly_salary <= 0) {
            return 'Månadslönen måste vara större än 0.';
        }
        
        if (isNaN(formData.retirement_age) || formData.retirement_age < 55 || formData.retirement_age > 75) {
            return 'Pensionsåldern måste vara mellan 55 och 75 år.';
        }
        
        if (formData.retirement_age <= formData.age) {
            return 'Pensionsåldern måste vara högre än din nuvarande ålder.';
        }
        
        if (isNaN(formData.growth) || formData.growth < 0 || formData.growth > 0.15) {
            return 'Tillväxten måste vara mellan 0% och 15%.';
        }
        
        if (isNaN(formData.salary_exchange) || formData.salary_exchange < 0) {
            return 'Löneväxlingen måste vara ett positivt tal.';
        }
        
        return null;
    }
    
    // Compare the agreements
    async function compareAgreements() {
        // Get form values
        const formData = getFormValues();
        
        // Validate inputs
        const validationError = validateInputs(formData);
        if (validationError) {
            showError(validationError);
            return;
        }
        
        try {
            // Call API for comparison data
            const response = await fetch('/api/compare', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(formData)
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.error || 'Fel vid jämförelsen.');
            }
            
            const data = await response.json();
            
            // Hide error if previously shown
            errorContainer.style.display = 'none';
            
            // Display comparison results
            displayComparisonResults(data.result, formData);
            
        } catch (error) {
            showError(error.message || 'Ett fel uppstod vid jämförelsen.');
            console.error('Comparison error:', error);
        }
    }
    
    // For development/testing - calculate comparison without API
    // This should be removed in production when API is working
    function calculateLocalComparison(formData) {
        // This is a simplified version for testing without backend
        // In production, we'll use the actual backend calculation
        
        const agreement1 = formData.agreement1;
        const scenario1 = formData.scenario1;
        const agreement2 = formData.agreement2;
        const scenario2 = formData.scenario2;
        
        // Get parameters for each agreement and scenario
        const params1 = pensionParameters[agreement1].scenarios[scenario1];
        const params2 = pensionParameters[agreement2].scenarios[scenario2];
        
        // Simple calculation for demonstration
        const age = formData.age;
        const salary = formData.monthly_salary;
        const retirementAge = formData.retirement_age;
        const yearsToRetirement = retirementAge - age;
        
        // Calculate for agreement 1
        let result1;
        if (scenario1 === 'Avd2') {
            // Simplified calculation for Avd2
            const percent = yearsToRetirement <= 30 ? 0.10 : 0.65;
            const monthlyPension = salary * percent;
            result1 = {
                monthly_pension: Math.round(monthlyPension),
                total_pension: Math.round(monthlyPension * 12 * 20),
                monthly_contribution: 0,
                years_to_pension: yearsToRetirement
            };
        } else {
            // Simplified calculation for other scenarios
            const contribution = salary * params1.contribution_rate_below_cap;
            const totalContribution = contribution * 12 * yearsToRetirement;
            // Very simplified growth calculation
            const totalWithGrowth = totalContribution * Math.pow(1 + formData.growth, yearsToRetirement/2);
            const monthlyPension = totalWithGrowth / (20 * 12);
            
            result1 = {
                monthly_pension: Math.round(monthlyPension),
                total_pension: Math.round(totalWithGrowth),
                monthly_contribution: Math.round(contribution),
                years_to_pension: yearsToRetirement
            };
        }
        
        // Calculate for agreement 2
        let result2;
        if (scenario2 === 'Avd2') {
            // Simplified calculation for Avd2
            const percent = yearsToRetirement <= 30 ? 0.10 : 0.65;
            const monthlyPension = salary * percent;
            result2 = {
                monthly_pension: Math.round(monthlyPension),
                total_pension: Math.round(monthlyPension * 12 * 20),
                monthly_contribution: 0,
                years_to_pension: yearsToRetirement
            };
        } else {
            // Simplified calculation for other scenarios
            const contribution = salary * params2.contribution_rate_below_cap;
            const totalContribution = contribution * 12 * yearsToRetirement;
            // Very simplified growth calculation
            const totalWithGrowth = totalContribution * Math.pow(1 + formData.growth, yearsToRetirement/2);
            const monthlyPension = totalWithGrowth / (20 * 12);
            
            result2 = {
                monthly_pension: Math.round(monthlyPension),
                total_pension: Math.round(totalWithGrowth),
                monthly_contribution: Math.round(contribution),
                years_to_pension: yearsToRetirement
            };
        }
        
        // Format the result similar to what backend would return
        return {
            agreement1: {
                name: agreement1,
                scenario: scenario1,
                ...result1
            },
            agreement2: {
                name: agreement2,
                scenario: scenario2,
                ...result2
            },
            differences: {
                monthly_pension_diff: calculatePercentDiff(result1.monthly_pension, result2.monthly_pension),
                total_pension_diff: calculatePercentDiff(result1.total_pension, result2.total_pension),
                monthly_contribution_diff: calculatePercentDiff(result1.monthly_contribution, result2.monthly_contribution)
            }
        };
    }
    
    // Helper function to calculate percentage difference
    function calculatePercentDiff(value1, value2) {
        if (value2 === 0) return value1 === 0 ? 0 : 100;
        return ((value1 - value2) / value2) * 100;
    }
    
    // Display an error message
    function showError(message) {
        errorContainer.textContent = message;
        errorContainer.style.display = 'block';
        resultsContainer.style.display = 'none';
    }
    
    // Display the comparison results
    function displayComparisonResults(result, formData) {
        // For local testing without API
        if (!result) {
            result = calculateLocalComparison(formData);
        }
        
        // Update headers
        document.getElementById('agreement1-header').textContent = 
            `${formData.agreement1} (${formData.scenario1})`;
        document.getElementById('agreement2-header').textContent = 
            `${formData.agreement2} (${formData.scenario2})`;
        
        // Extract result data
        const result1 = result.agreement1 || {};
        const result2 = result.agreement2 || {};
        const differences = result.differences || {};
        
        // Update table values
        updateTableValue('monthly-pension1', result1.monthly_pension);
        updateTableValue('monthly-pension2', result2.monthly_pension);
        updateTableValue('monthly-pension-diff', formatDifference(differences.monthly_pension_diff));
        
        updateTableValue('total-pension1', result1.total_pension);
        updateTableValue('total-pension2', result2.total_pension);
        updateTableValue('total-pension-diff', formatDifference(differences.total_pension_diff));
        
        updateTableValue('monthly-contribution1', result1.monthly_contribution);
        updateTableValue('monthly-contribution2', result2.monthly_contribution);
        updateTableValue('monthly-contribution-diff', formatDifference(differences.monthly_contribution_diff));
        
        updateTableValue('years-to-pension1', result1.years_to_pension);
        updateTableValue('years-to-pension2', result2.years_to_pension);
        if (result1.years_to_pension === result2.years_to_pension) {
            updateTableValue('years-to-pension-diff', '(samma)');
        } else {
            updateTableValue('years-to-pension-diff', 
                `${result1.years_to_pension > result2.years_to_pension ? '+' : ''}${result1.years_to_pension - result2.years_to_pension} år`);
        }
        
        // Create and display charts
        createBarChart('pension-chart', 
            [
                { label: `${formData.agreement1} (${formData.scenario1})`, value: result1.monthly_pension },
                { label: `${formData.agreement2} (${formData.scenario2})`, value: result2.monthly_pension }
            ],
            'kr/mån');
            
        createBarChart('contribution-chart', 
            [
                { label: `${formData.agreement1} (${formData.scenario1})`, value: result1.monthly_contribution },
                { label: `${formData.agreement2} (${formData.scenario2})`, value: result2.monthly_contribution }
            ],
            'kr/mån');
        
        // Generate summary
        generateSummary(result, formData);
        
        // Show results
        resultsContainer.style.display = 'block';
    }
    
    // Update a table cell with formatted value
    function updateTableValue(id, value) {
        const element = document.getElementById(id);
        if (!element) return;
        
        // Format numbers with thousands separator
        if (typeof value === 'number') {
            element.textContent = value.toLocaleString('sv-SE');
        } else {
            element.textContent = value;
        }
        
        // Add CSS classes for difference cells
        if (id.endsWith('-diff') && typeof value === 'string' && value.includes('%')) {
            const numValue = parseFloat(value);
            element.className = '';
            if (numValue > 0) {
                element.classList.add('positive-diff');
            } else if (numValue < 0) {
                element.classList.add('negative-diff');
            } else {
                element.classList.add('neutral-diff');
            }
        }
    }
    
    // Format a difference value
    function formatDifference(value) {
        if (value === 0) return '0%';
        return `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
    }
    
    // Create a simple bar chart
    function createBarChart(containerId, data, unit) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        container.innerHTML = '';
        
        // Find max value for scaling
        const maxValue = Math.max(...data.map(item => item.value));
        
        // Create chart container
        const chartElement = document.createElement('div');
        chartElement.className = 'bar-chart';
        
        // Create a bar for each data point
        data.forEach(item => {
            // Create row container
            const rowElement = document.createElement('div');
            rowElement.className = 'bar-row';
            
            // Create label
            const labelElement = document.createElement('div');
            labelElement.className = 'bar-label';
            labelElement.textContent = item.label;
            
            // Create bar container
            const barContainerElement = document.createElement('div');
            barContainerElement.className = 'bar-container';
            
            // Create the actual bar
            const barElement = document.createElement('div');
            barElement.className = 'bar';
            const percentage = maxValue > 0 ? (item.value / maxValue) * 100 : 0;
            barElement.style.width = `${percentage}%`;
            
            // Create value display
            const valueElement = document.createElement('div');
            valueElement.className = 'bar-value';
            valueElement.textContent = `${item.value.toLocaleString('sv-SE')} ${unit}`;
            
            // Add elements to row
            barContainerElement.appendChild(barElement);
            rowElement.appendChild(labelElement);
            rowElement.appendChild(barContainerElement);
            rowElement.appendChild(valueElement);
            
            // Add row to chart
            chartElement.appendChild(rowElement);
        });
        
        // Add chart to container
        container.appendChild(chartElement);
    }
    
    // Generate summary text based on comparison results
    function generateSummary(result, formData) {
        const summaryContainer = document.getElementById('comparison-summary');
        if (!summaryContainer) return;
        
        // Extract values for summary
        const agreement1 = formData.agreement1;
        const scenario1 = formData.scenario1;
        const agreement2 = formData.agreement2;
        const scenario2 = formData.scenario2;
        
        const result1 = result.agreement1 || {};
        const result2 = result.agreement2 || {};
        const differences = result.differences || {};
        
        const summaryPoints = [];
        
        // Determine which pension is better
        if (differences.monthly_pension_diff > 1) {
            // Agreement 1 gives better pension
            summaryPoints.push(`<li><strong>${agreement1} (${scenario1})</strong> ger en <strong>${differences.monthly_pension_diff.toFixed(1)}% högre månadspension</strong> jämfört med ${agreement2} (${scenario2}).</li>`);
        } else if (differences.monthly_pension_diff < -1) {
            // Agreement 2 gives better pension
            summaryPoints.push(`<li><strong>${agreement2} (${scenario2})</strong> ger en <strong>${Math.abs(differences.monthly_pension_diff).toFixed(1)}% högre månadspension</strong> jämfört med ${agreement1} (${scenario1}).</li>`);
        } else {
            // Approximately equal
            summaryPoints.push(`<li>Båda avtalen ger <strong>likvärdig månadspension</strong> med en skillnad på mindre än 1%.</li>`);
        }
        
        // Add information about contributions if relevant
        if (result1.monthly_contribution > 0 && result2.monthly_contribution > 0) {
            if (differences.monthly_contribution_diff > 1) {
                summaryPoints.push(`<li>${agreement1} (${scenario1}) har <strong>${differences.monthly_contribution_diff.toFixed(1)}% högre månatlig avsättning</strong> än ${agreement2} (${scenario2}).</li>`);
            } else if (differences.monthly_contribution_diff < -1) {
                summaryPoints.push(`<li>${agreement2} (${scenario2}) har <strong>${Math.abs(differences.monthly_contribution_diff).toFixed(1)}% högre månatlig avsättning</strong> än ${agreement1} (${scenario1}).</li>`);
            }
            
            // Calculate and compare efficiency (pension per contributed krona)
            if (result1.monthly_contribution > 0 && result2.monthly_contribution > 0) {
                const efficiency1 = result1.monthly_pension / result1.monthly_contribution;
                const efficiency2 = result2.monthly_pension / result2.monthly_contribution;
                const efficiencyDiff = ((efficiency1 - efficiency2) / efficiency2) * 100;
                
                if (Math.abs(efficiencyDiff) > 5) {
                    if (efficiencyDiff > 0) {
                        summaryPoints.push(`<li>${agreement1} (${scenario1}) ger <strong>mer pension per insatt krona</strong> jämfört med ${agreement2} (${scenario2}).</li>`);
                    } else {
                        summaryPoints.push(`<li>${agreement2} (${scenario2}) ger <strong>mer pension per insatt krona</strong> jämfört med ${agreement1} (${scenario1}).</li>`);
                    }
                }
            }
        }
        
        // Add note about shared parameters
        summaryPoints.push(`<li>Beräkningen är baserad på: ålder ${formData.age}, månadslön ${formData.monthly_salary.toLocaleString('sv-SE')} kr, pensionsålder ${formData.retirement_age}, tillväxt ${(formData.growth * 100).toFixed(1)}%.</li>`);
        
        // Add disclaimer
        summaryPoints.push(`<li><em>Obs: Beräkningarna är ungefärliga. Faktiska utfall beror på många faktorer såsom löneökning, faktisk avkastning och avtalsförändringar.</em></li>`);
        
        // Update the summary container
        summaryContainer.innerHTML = `<ul>${summaryPoints.join('')}</ul>`;
    }
    
    // Public methods
    return {
        init: init
    };
})();

// Initialize comparison module when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    PensionComparison.init();
});
