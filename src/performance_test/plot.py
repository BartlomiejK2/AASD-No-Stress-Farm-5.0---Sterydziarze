import pandas as pd
import matplotlib.pyplot as plt

INPUT_CSV = "data/summary.csv"
OUT_CPU_AVG = "data/cpu_avg.png"
OUT_CPU_MAX = "data/cpu_max.png"
OUT_RAM_AVG = "data/ram_avg.png"
OUT_RAM_MAX = "data/ram_max.png"

df = pd.read_csv(INPUT_CSV)

num_cols = ["cpu_avg", "cpu_max", "ram_avg", "ram_max"]
df[num_cols] = df[num_cols].astype(float)

df = df.sort_values("cows_count")

cows = df[df["group"] == "cows"]
xmpp = df[df["group"] == "xmpp"]

plt.figure(figsize=(8, 5))
plt.plot(
    cows["cows_count"], cows["cpu_avg"],
    marker="o", label="krowy", color="#8E3939"
)
plt.plot(
    xmpp["cows_count"], xmpp["cpu_avg"],
    marker="s", label="XMPP", color="#F2E01D"
)

plt.xlabel("Liczba krów")
plt.ylabel("Średnie zużycie CPU [%]")
plt.title("Średnie zużycie CPU w zależności od liczby krów")
plt.legend()
plt.grid(True)

plt.tight_layout()
plt.savefig(OUT_CPU_AVG, dpi=150)
plt.close()

plt.figure(figsize=(8, 5))
plt.plot(
    cows["cows_count"], cows["cpu_max"],
    marker="o", label="krowy", color="#8E3939"
)
plt.plot(
    xmpp["cows_count"], xmpp["cpu_max"],
    marker="s", label="XMPP", color="#F2E01D"
)

plt.xlabel("Liczba krów")
plt.ylabel("Maksymalne zużycie CPU [%]")
plt.title("Maksymalne zużycie CPU w zależności od liczby krów")
plt.legend()
plt.grid(True)

plt.tight_layout()
plt.savefig(OUT_CPU_MAX, dpi=150)
plt.close()

plt.figure(figsize=(8, 5))
plt.plot(
    cows["cows_count"], cows["ram_avg"],
    marker="o", label="krowy", color="#8E3939"
)
plt.plot(
    xmpp["cows_count"], xmpp["ram_avg"],
    marker="s", label="XMPP", color="#F2E01D"
)

plt.xlabel("Liczba krów")
plt.ylabel("Średnie zużycie RAM [MiB]")
plt.title("Średnie zużycie RAM w zależności od liczby krów")
plt.legend()
plt.grid(True)

plt.tight_layout()
plt.savefig(OUT_RAM_AVG, dpi=150)
plt.close()

plt.figure(figsize=(8, 5))
plt.plot(
    cows["cows_count"], cows["ram_max"],
    marker="o", label="krowy", color="#8E3939"
)
plt.plot(
    xmpp["cows_count"], xmpp["ram_max"],
    marker="s", label="XMPP", color="#F2E01D"
)

plt.xlabel("Liczba krów")
plt.ylabel("Maksymalne zużycie RAM [MiB]")
plt.title("Maksymalne zużycie RAM w zależności od liczby krów")
plt.legend()
plt.grid(True)

plt.tight_layout()
plt.savefig(OUT_RAM_MAX, dpi=150)
plt.close()

print("Wygenerowano wykresy:")
print(" -", OUT_CPU_AVG)
print(" -", OUT_CPU_MAX)
print(" -", OUT_RAM_AVG)
print(" -", OUT_RAM_MAX)
