from enum import Enum

class EventStatus(str, Enum):
    DETECTED = "DETECTED"
    VERIFYING = "VERIFYING"
    CONFIRMED = "CONFIRMED"
    FALSE_POSITIVE = "FALSE_POSITIVE"
    NEEDS_REVIEW = "NEEDS_REVIEW"

class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class VerifiedBy(str, Enum):
    NONE = "NONE"
    AI = "AI"
    HUMAN = "HUMAN"

class SourceType(str, Enum):
    WEBCAM = "WEBCAM"
    FILE = "FILE"
    RTSP = "RTSP"

class MediaKind(str, Enum):
    KEYFRAME = "KEYFRAME"
    CROP = "CROP"
    CLIP = "CLIP"

class HumanAction(str, Enum):
    CONFIRM = "CONFIRM"
    MARK_FALSE_POSITIVE = "MARK_FALSE_POSITIVE"
    REOPEN = "REOPEN"

class VlmStatus(str, Enum):
    OK = "OK"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    TIMEOUT = "TIMEOUT"
    UNAVAILABLE = "UNAVAILABLE"
    SKIPPED_QUEUE_FULL = "SKIPPED_QUEUE_FULL"

class JobStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"
    CANCELED = "CANCELED"

class ErrorCode(str, Enum):
    BAD_REQUEST = "bad_request"
    UNAUTHORIZED = "unauthorized"
    FORBIDDEN = "forbidden"
    LOOPBACK_ONLY = "loopback_only"
    NOT_FOUND = "not_found"
    EVENT_ID_CONFLICT = "event_id_conflict"
    INVALID_STATE_TRANSITION = "invalid_state_transition"
    EVENT_REVIEWED = "event_reviewed"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    VALIDATION_ERROR = "validation_error"
    RATE_LIMITED = "rate_limited"
    SERVICE_UNAVAILABLE = "service_unavailable"
    INTERNAL_ERROR = "internal_error"
