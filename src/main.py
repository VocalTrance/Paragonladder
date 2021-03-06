from analyzer import Analyzer
from collector import Collector
from constants import Locale, regions, track_count
from diablo_api import DiabloApi
from database import Database
from blizzardapi import BlizzardApi
import argparse
from pages import make_site

parser = argparse.ArgumentParser()
parser.add_argument("--client_id")
parser.add_argument("--client_secret")

args = vars(parser.parse_args())
if not args["client_id"] or not args["client_secret"]:
    print("No client id or secret given.")
    quit()


client_id = args["client_id"]
client_secret = args["client_secret"]

api = DiabloApi(BlizzardApi(client_id, client_secret), Locale.EN_US)
for region in regions:
    print(f">>> {region}")
    try:
        current_season = api.get_current_season(region)
        if not current_season:
            print(f"Failed to get current season, skipping the region.")
            continue

        db = Database(current_season, region)
        collector = Collector(current_season, region, api)
        analyzer = Analyzer(current_season, region)

        # Update the tracked accounts infos
        battletags = db.get_tracked_battltags()
        accounts = collector.collect_accounts(battletags)
        infos = analyzer.analyze_accounts(accounts)
        db.update_tracked(infos)

        # Collect battletags from all leaderboards
        btags = collector.collect_battletags()
        print(f"Collected a total of {len(btags)} unique battletags.")

        # Determine which new accounts to track
        tracked = {a.battletag: a.paragon_season for a in db.get_tracked()}

        # If there are more accounts tracked than is allowed
        if len(tracked) > track_count:
            descending_tuples = sorted(tracked.items(), key=lambda x: x[1], reverse=True)
            tracked = dict(descending_tuples[:track_count])
            for btag, _ in descending_tuples[track_count - 1 :]:
                db.remove_tracked_account(btag)
        # If there arent as many accounts tracked as is allowed, insert dummies
        elif len(tracked) < track_count:
            for i in range(track_count - len(tracked)):
                tracked[i] = 0

        # Ascending by paragon
        tracked = dict(sorted(tracked.items(), key=lambda item: item[1]))

        new_battletags = []
        remove_if_new_collected = {}
        for btag, p in btags:
            if p > list(tracked.values())[0] and btag not in tracked.keys():
                new_battletags.append(btag)
                tracked[btag] = p

                # Remove trumped battletag
                trumped_btag = list(tracked.keys())[0]
                del tracked[trumped_btag]
                remove_if_new_collected[btag] = trumped_btag

                tracked = dict(sorted(tracked.items(), key=lambda item: item[1]))

        print(
            f"Found {len(new_battletags)} accounts whose leaderboard paragon trumps the paragon of those tracked."
        )

        # Inserts new accounts to track
        accounts = collector.collect_accounts(new_battletags)
        infos = analyzer.analyze_accounts(accounts)
        db.update_tracked(infos)

        # Remove accounts to untrack
        for new, old in remove_if_new_collected.items():
            # If an account could be collected for the new battletag. To circumvent mysterious "Downstream error"
            if len([a for a in accounts if a.battleTag == new]) > 0:
                db.remove_tracked_account(old)
    except Exception as e:
        print(str(e))

make_site()
