import { FilesDropzone } from '@/components/ui/files-dropzone'

import { useUploadResumes } from './api'

/** Upload one or many resumes to a job; reports per-file problems without failing the rest. */
export function AddResumes({ jobId }: { jobId: string }) {
  const upload = useUploadResumes(jobId)
  const result = upload.data
  return (
    <div className="space-y-2">
      <FilesDropzone
        label="Resume PDFs"
        hint="One or many PDFs · up to 10 MB each"
        accept="application/pdf,.pdf"
        onFiles={(files) => upload.mutate(files)}
        disabled={upload.isPending}
        compact
      />
      <div aria-live="polite" className="text-sm">
        {upload.isPending && <p className="text-muted-foreground">Uploading…</p>}
        {upload.isError && (
          <p role="alert" className="text-destructive">
            {upload.error.message}
          </p>
        )}
        {result && !upload.isPending && (
          <div className="space-y-1">
            {result.added.length > 0 && (
              <p className="text-muted-foreground">
                Added {result.added.length} {result.added.length === 1 ? 'resume' : 'resumes'};
                scoring starts in the background.
              </p>
            )}
            {result.errors.map((e) => (
              <p key={e.filename} role="alert" className="text-destructive">
                {e.filename}: {e.message}
              </p>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
