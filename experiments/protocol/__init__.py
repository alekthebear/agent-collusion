"""Two-agent tool protocol internals."""

MEMORY_SCOPE = "cross-episode"

# Default communication rounds; all configured rounds run.
DEFAULT_MAX_ROUNDS = 5

# send_message's optional message_type label is shown to the receiver but was never
# counted toward the character limit, so it can carry a whole raw log.
# open: as in the paper. off: no label field, and incoming messages carry no
# [type=...] tag.
MESSAGE_SIDE_CHANNELS = ("open", "off")


# Separate task and delivery budgets so task complexity does not reduce channel retries.
TASK_ATTEMPTS = 15
COMMUNICATION_ATTEMPTS = 3

# Per-agent retries for malformed verdict submissions.
VERDICT_ATTEMPTS = 3
