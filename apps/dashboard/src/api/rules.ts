export type Point = [number, number];
export type CameraGeometry = {
  snapshot_width: number;
  snapshot_height: number;
  zones: Record<string, Point[]>;
  lines: Record<string, [Point, Point]>;
  homography: number[][] | null;
};

export type RuleSpec = {
  rule_id: string;
  camera_id: string;
  version: number;
  name: string;
  entity: string;
  when: unknown;
  support_level: 'SUPPORTED' | 'EXPERIMENTAL' | 'UNSUPPORTED';
  status: 'draft' | 'active' | 'disabled';
  needs_visual_review: boolean;
  unsupported_reason?: string | null;
};

export type RuleRecord = {
  id: string;
  camera_id: string;
  text: string;
  spec: RuleSpec;
  readback: string | null;
  readback_hash: string | null;
  can_activate: boolean;
  status: RuleSpec['status'];
  version: number;
};

export type CompileResult = {
  spec: RuleSpec;
  readback: string | null;
  readback_hash: string | null;
  support_level: RuleSpec['support_level'];
  problems: string[];
  can_activate: boolean;
};
