# Patch for Skima's PII scrubber (not applied)

Fixes the bug the stress-test review found in Skima's
`engines/employer/app/services/pii_removal_service/pii_removal.rb`: a case-insensitive
substring replace, so a candidate named "Ruby" turned "Ruby on Rails" into
"<PII> on Rails", "Al" broke "Rational", and phones only matched in the stored format.

Not applied to `Z:\Skima` because that working tree is on another feature branch with
uncommitted changes, and Ruby/RSpec are not installed in this environment, so the spec
could not be run. To apply, from a clean branch in skima-platform-api:

    cp -r <jd-scorer>/eval/stress/skima_patch/engines <jd-scorer>/eval/stress/skima_patch/spec .
    bundle exec rspec spec/service_objects/pii_removal_service/pii_removal_spec.rb

Same public interface (`new(text, details).remove_pii`, `get_text`,
`get_candidate_details`); accepts string or symbol keys, as the existing callers pass both.
