import { redirect } from 'next/navigation';

// Compatibility entry point. The canonical dashboard is served by the PC API.
export default function Page() {
  redirect(process.env.SAFESPACE_SERVER_URL || 'http://localhost:8000');
}
