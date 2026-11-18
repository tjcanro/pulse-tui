"""A single cached geometry provider, independent of palettes and camera modes."""
from .ribbons import Ribbons
from .orbit import Orbit
from .filaments import Filaments

FACTORIES = {"ribbons": Ribbons, "orbit": Orbit, "filaments": Filaments}


class SpatialScenes:
    def __init__(self):
        self.key = self.model = None

    def evaluate(self, audio, now, options):
        key = (options.scene, options.density)
        if key != self.key:
            self.model = FACTORIES[options.scene](options.density)
            self.key = key
        return self.model.evaluate(audio, now, options)
