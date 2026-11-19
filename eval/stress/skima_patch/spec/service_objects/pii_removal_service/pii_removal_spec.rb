require "rails_helper"

RSpec.describe PiiRemovalService::PiiRemoval do
  def scrub(text, details)
    described_class.new(text, details).remove_pii
  end

  it "keeps a skill that equals the candidate's first name" do
    text = "Ruby Castellanos\nBackend engineer\nBuilt tools in Ruby on Rails and Ruby."
    out = scrub(text, first_name: "Ruby", last_name: "Castellanos")
    expect(out).to eq("<PII>\nBackend engineer\nBuilt tools in Ruby on Rails and Ruby.")
  end

  it "never replaces a short name inside other words" do
    text = "Al Smith\nRational, analytical, global thinker. Al led the team."
    out = scrub(text, "first_name" => "Al", "last_name" => "Smith")
    expect(out).to eq("<PII>\nRational, analytical, global thinker. Al led the team.")
  end

  it "replaces the full name anywhere, in any case and as 'Last, First'" do
    text = "Resume\nPRIYA SHARMA\nReferences: Sharma, Priya. Signed priya  sharma"
    out = scrub(text, first_name: "Priya", last_name: "Sharma")
    expect(out).to eq("Resume\n<PII>\nReferences: <PII>. Signed <PII>")
  end

  it "replaces a name split over two header lines" do
    text = "PRIYA\nSHARMA\nNurse at Priya Street Clinic"
    out = scrub(text, first_name: "Priya", last_name: "Sharma")
    expect(out).to eq("<PII>\nNurse at Priya Street Clinic")
  end

  it "replaces a lone name only when it stands on its own line" do
    text = "Priya\nRegistered nurse\nTrained at Priya Street Clinic"
    out = scrub(text, first_name: "Priya", last_name: "Sharma")
    expect(out).to eq("<PII>\nRegistered nurse\nTrained at Priya Street Clinic")
  end

  it "matches the phone by digits whatever the formatting" do
    text = "Call +1 (555) 123-4567 or 555.123.4567. Revenue 1,234,567."
    out = scrub(text, first_name: "Jo", last_name: "Lee", phone: "5551234567")
    expect(out).to eq("Call <PII> or <PII>. Revenue 1,234,567.")
  end

  it "replaces email and other values as whole words" do
    text = "jo.lee@example.com | Austin\nWorked with Austin-based teams"
    out = scrub(text, first_name: "Jo", last_name: "Lee", email: "jo.lee@example.com", city: "Austin")
    expect(out).to eq("<PII> | <PII>\nWorked with <PII>-based teams")
  end

  it "handles nil and blank details" do
    expect(scrub("Some text", first_name: nil, last_name: "", phone: nil)).to eq("Some text")
  end
end
