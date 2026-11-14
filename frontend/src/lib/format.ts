const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })

/** "14 Nov 2026, 11:13" in the viewer's locale. */
export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso))
}
