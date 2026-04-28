def map_distance_to_confidence(dist):
    if dist <= 0:
        return 100, "Exact or very strong match"
    elif dist <= 8:
        val = 100 - dist
        return int(val), "Strong perceptual similarity with official asset"
    elif dist <= 14:
        val = 90 - (dist - 8) * 2
        return int(val), "Likely match with minor modifications"
    elif dist <= 20:
        val = 74 - (dist - 14) * 4
        return int(val), "Weak match, significant differences observed"
    elif dist <= 25:
        val = 50 - (dist - 20) * 5
        return int(val), "Very weak semantic match, heavily altered or different perspective"
    else:
        return 0, "No match"
