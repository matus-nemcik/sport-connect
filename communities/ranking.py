from accounts.models import User, stats_for


def ranking(users):
    """Users ordered by points (FR6). Ties: more exact scores first, then name.

    Returns a list of dicts with rank, user and stats; tied users share a rank.
    """
    users = list(users)
    stats = stats_for(User.objects.filter(pk__in=[u.pk for u in users]))
    rows = sorted(
        ({"user": u, "stats": stats[u.pk]} for u in users),
        key=lambda r: (-r["stats"]["points"], -r["stats"]["exact"], r["user"].nickname.lower()),
    )
    prev, rank = None, 0
    for i, row in enumerate(rows, start=1):
        key = (row["stats"]["points"], row["stats"]["exact"])
        if key != prev:
            rank, prev = i, key
        row["rank"] = rank
    return rows


def community_ranking(community):
    return ranking(community.members.all())
