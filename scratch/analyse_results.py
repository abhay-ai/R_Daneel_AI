import json
import numpy as np

def analyze_report(filepath):
    with open(filepath, 'r') as f:
        data = json.load(f)
    
    results = data["results"]
    total = len(results)
    passed = sum(1 for r in results if r["success"])
    
    # Calculate overall stats
    pass_rate = (passed / total) * 100
    times = [r["time"] for r in results]
    retries = [r["retries"] for r in results]
    avg_time = np.mean(times)
    avg_retries = np.mean(retries)
    
    # Tier breakdown
    tiers = {}
    for r in results:
        # Group by 100-Elo tier
        tier = (r["rating"] // 100) * 100
        if tier not in tiers:
            tiers[tier] = []
        tiers[tier].append(r)
        
    tier_stats = {}
    for tier in sorted(tiers.keys()):
        tier_results = tiers[tier]
        t_total = len(tier_results)
        t_passed = sum(1 for r in tier_results if r["success"])
        t_pass_rate = (t_passed / t_total) * 100
        tier_stats[tier] = {
            "passed": t_passed,
            "total": t_total,
            "pass_rate": t_pass_rate
        }
        
    return {
        "pass_rate": pass_rate,
        "avg_time": avg_time,
        "avg_retries": avg_retries,
        "tier_stats": tier_stats,
        "estimated_elo": data.get("estimated_elo", "N/A")
    }

print("=== BASELINE REPORT ===")
baseline = analyze_report("logs/large_scale_report_baseline_500.json")
print(f"Pass Rate: {baseline['pass_rate']:.2f}% ({baseline['estimated_elo']} Elo)")
print(f"Avg Time: {baseline['avg_time']:.2f}s")
print(f"Avg Retries: {baseline['avg_retries']:.2f}")
print("Tier stats:")
for tier, stats in baseline["tier_stats"].items():
    print(f"  {tier}s: {stats['passed']}/{stats['total']} ({stats['pass_rate']:.2f}%)")

print("\n=== NEURO-SYMBOLIC REPORT ===")
ns = analyze_report("logs/large_scale_report_neuro_symbolic_500.json")
print(f"Pass Rate: {ns['pass_rate']:.2f}% ({ns['estimated_elo']} Elo)")
print(f"Avg Time: {ns['avg_time']:.2f}s")
print(f"Avg Retries: {ns['avg_retries']:.2f}")
print("Tier stats:")
for tier, stats in ns["tier_stats"].items():
    print(f"  {tier}s: {stats['passed']}/{stats['total']} ({stats['pass_rate']:.2f}%)")
