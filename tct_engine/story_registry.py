from __future__ import annotations

import json
from pathlib import Path


class StoryRegistry:

    def __init__(self, filename="story-registry.json"):

        self.path = Path(filename)

        if self.path.exists():

            self.data = json.loads(self.path.read_text())

        else:

            self.data = {
                "schema": 1,
                "next_story_id": 1,
                "stories": {},
                "event_to_story": {},
                "story_aliases": {}
}
            

    def save(self):

        self.path.write_text(
            json.dumps(
                self.data,
                indent=2,
                ensure_ascii=False
            )
        )

    def resolve_story(self, event_key):

        mapping = self.data["event_to_story"]

        if event_key in mapping:

            return mapping[event_key]

        story_id = f"story_{self.data['next_story_id']:06d}"

        self.data["next_story_id"] += 1

        mapping[event_key] = story_id

        self.data["stories"][story_id] = {
            "story_id": story_id,
            "events": [event_key],
            "status": "developing"
        }

        self.save()

        return story_id

    def attach_event(self, story_id, event_key):

        story = self.data["stories"][story_id]

        if event_key not in story["events"]:

            story["events"].append(event_key)

        self.data["event_to_story"][event_key] = story_id

        self.save()
        def merge_events(
        self,
        primary_event: str,
        secondary_event: str,
    ):
        """
        Merge two event keys into one persistent story.
        """

        primary_story = self.resolve_story(primary_event)
        secondary_story = self.resolve_story(secondary_event)

        if primary_story == secondary_story:
            return primary_story

        primary = self.data["stories"][primary_story]
        secondary = self.data["stories"][secondary_story]

        for event in secondary["events"]:

            if event not in primary["events"]:
                primary["events"].append(event)

            self.data["event_to_story"][event] = primary_story

        self.data["story_aliases"][secondary_story] = primary_story

        del self.data["stories"][secondary_story]

        self.save()

        return primary_story
