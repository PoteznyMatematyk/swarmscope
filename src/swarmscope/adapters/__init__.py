"""Source adapters: each maps raw files onto the unified schema."""

from . import ai_village, collusion_wiki

ADAPTERS = {
    collusion_wiki.SOURCE: collusion_wiki,
    ai_village.SOURCE: ai_village,
}
