"""
Our 1R1C house parameters derived from the team's standard-house baseline v2 specification
(baseline_v2/README.md, "Model and sources" sheet of US_home_energy_comparison.xlsx; ISO 13790 reference home).

    derive(floor_area_m2, stories=1) -> dict of house keys used by common.py / case1 / case2

v2 geometry: footprint = floor area / stories, 1.25 aspect ratio, 8 ft story height, windows 20.83 % of gross wall
(300 ft2 at 2,000 ft2), 40 ft2 of doors. Effective R-20 walls, R-49 ceiling, R-30 floor (vented crawlspace at
outdoor temperature), R-5 doors, U-0.30 / SHGC 0.30 windows (angular factor 0.9, shading 0.7), 0.35 ACH,
ISO 13790 "light" mass 110 kJ/K per m2 floor, RESNET 301 internal gains (3 bedrooms, 85 % sensible).

Our model is one node, so v2's surface-resolved solar is folded into one aperture on global horizontal irradiance,
assuming the four-face mean vertical irradiance is about half of GHI, and ISO 13790 sky long-wave loss
(h_r 4.5 W/m2K, dT_sky 11 K for mid latitudes) becomes a constant loss.
"""
FT2_PER_M2 = 10.7639
W_PER_FT2_PER_R = 5.678263 / FT2_PER_M2       # U [W/m2K] = 5.678/R_US; area ft2 -> m2
RHO_CP_AIR = 1.2 * 1006                       # J/m3K
BTU_DAY_TO_W = 1055.06 / 86400

V2 = dict(aspect=1.25, story_height_ft=8.0, window_to_gross_wall=300 / 1440, door_ft2=40.0,
          R_wall=20.0, R_ceiling=49.0, R_floor=30.0, R_door=5.0, U_window_US=0.30, SHGC=0.30,
          angular=0.9, shading=0.7, ach=0.35, mass_kJ_per_K_m2=110.0, bedrooms=3, sensible_fraction=0.85,
          wall_alpha=0.5, roof_alpha=0.4, h_out=20.0, h_r=4.5, dT_sky=11.0, vertical_to_ghi=0.5)


def derive(floor_area_m2, stories=1, p=V2):
    a_ft2 = floor_area_m2 * FT2_PER_M2
    fp = a_ft2 / stories
    L = (fp * p["aspect"]) ** 0.5
    W = fp / L
    gross_wall = 2 * (L + W) * p["story_height_ft"] * stories
    windows = p["window_to_gross_wall"] * gross_wall
    opaque = gross_wall - windows - p["door_ft2"]
    H_wall = opaque / p["R_wall"] * W_PER_FT2_PER_R
    H_roof = fp / p["R_ceiling"] * W_PER_FT2_PER_R
    H_floor = fp / p["R_floor"] * W_PER_FT2_PER_R
    H_door = p["door_ft2"] / p["R_door"] * W_PER_FT2_PER_R
    H_win = windows * p["U_window_US"] * W_PER_FT2_PER_R
    volume_m3 = a_ft2 * p["story_height_ft"] / FT2_PER_M2 / 3.28084
    H_ve = volume_m3 * p["ach"] / 3600 * RHO_CP_AIR
    gains_total_W = (17900 + 23.8 * a_ft2 + 4104 * p["bedrooms"]) * BTU_DAY_TO_W
    win_m2 = windows / FT2_PER_M2
    aperture = (win_m2 * p["SHGC"] * p["angular"] * p["shading"] * p["vertical_to_ghi"]
                + H_roof * p["roof_alpha"] / p["h_out"]
                + H_wall * p["wall_alpha"] / p["h_out"] * p["vertical_to_ghi"])
    sky_loss_W = (1 / p["h_out"]) * p["h_r"] * p["dT_sky"] * (H_roof + 0.5 * H_wall + 0.5 * H_win)
    return dict(
        floor_area_m2=floor_area_m2, stories=stories,
        wall_area_m2=round(opaque / FT2_PER_M2, 2),
        wall_U_W_m2K=round(1 / (p["R_wall"] * 0.1761), 4),
        UA_total_kW_per_K=round((H_wall + H_roof + H_floor + H_door + H_win + H_ve) / 1000, 4),
        thermal_mass_kWh_per_K=round(p["mass_kJ_per_K_m2"] * floor_area_m2 / 3600, 3),
        internal_gains_kW=round(gains_total_W * p["sensible_fraction"] / 1000, 4),
        internal_sensible_fraction=p["sensible_fraction"],
        solar_aperture_m2=round(aperture, 3),
        sky_loss_kW=round(sky_loss_W / 1000, 4),
        volume_m3=round(volume_m3, 1), air_changes_per_hour=p["ach"],
    )


if __name__ == "__main__":
    import json
    for a in (150, 2000 / FT2_PER_M2):
        print(round(a * FT2_PER_M2), "ft2:", json.dumps(derive(a)))
