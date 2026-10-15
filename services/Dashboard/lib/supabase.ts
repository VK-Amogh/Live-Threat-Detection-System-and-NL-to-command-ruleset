import { createClient } from '@supabase/supabase-js';

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL || 'https://hvdqlslmjyskuctkqpyr.supabase.co';
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY || 'sb_publishable_gSnkSDi-2tjHrl8YBXNxtQ_FVQfxyPN';

export const supabase = createClient(supabaseUrl, supabaseAnonKey);
