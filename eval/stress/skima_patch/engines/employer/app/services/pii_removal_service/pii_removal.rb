module PiiRemovalService
  # Replaces the candidate's known PII (from the DB record) in resume text with <PII>.
  #
  # Rules (why: the old version did a case-insensitive substring replace, so a candidate
  # named "Ruby" turned "Ruby on Rails" into "<PII> on Rails" and "Al" broke "Rational"):
  # 1. The full name ("first last") is replaced first, as whole words, anywhere.
  # 2. A lone first or last name is replaced only where it stands on a line by itself
  #    (e.g. "PRIYA" / "SHARMA" on two header lines). Inside sentences a lone first name is
  #    far more often a skill or a place (Ruby, Sydney, Austin) than the person.
  # 3. Phones are matched by digits, so "+1 (555) 123-4567" matches a stored "5551234567".
  # 4. Other values (email, address, city) are replaced as whole words.
  class PiiRemoval
    TOKEN = "<PII>".freeze
    PHONE_LIKE = /\+?\(?\d[\d\s().-]{5,}\d/
    PHONE_MATCH_DIGITS = 10 # compare the last 10 digits: ignores country code / trunk 0

    def initialize(text, candidate_details)
      @text = text.to_s
      @candidate_details = (candidate_details || {}).to_h.transform_keys(&:to_s)
    end

    def remove_pii
      first = value("first_name")
      last = value("last_name")
      replace_everywhere!("#{first} #{last}") if first && last
      replace_everywhere!("#{last}, #{first}") if first && last
      [first, last].compact.each { |name| replace_standalone!(name) }
      replace_phone!(value("phone"))
      @candidate_details.each do |key, raw|
        next if %w[first_name last_name phone].include?(key)
        v = raw.is_a?(String) ? raw.strip : nil
        replace_everywhere!(v) if v && !v.empty?
      end
      @text
    end

    def get_text
      @text
    end

    def get_candidate_details
      @candidate_details
    end

    private

    def value(key)
      v = @candidate_details[key]
      v = v.strip if v.is_a?(String)
      v.is_a?(String) && !v.empty? ? v : nil
    end

    # Whole-word, case-insensitive; any run of whitespace between words matches.
    def word_regex(value)
      words = value.split(/\s+/).map { |w| Regexp.escape(w) }
      /(?<![[:alnum:]])#{words.join('\s+')}(?![[:alnum:]])/i
    end

    def replace_everywhere!(value)
      @text = @text.gsub(word_regex(value), TOKEN)
    end

    # Only lines that are just the name (plus punctuation or already-replaced tokens).
    def replace_standalone!(name)
      regex = word_regex(name)
      @text = @text.split("\n", -1).map do |line|
        rest = line.gsub(regex, "").gsub(TOKEN, "").gsub(/[^[:alnum:]]/, "")
        line.match?(regex) && rest.empty? ? line.gsub(regex, TOKEN) : line
      end.join("\n")
    end

    def replace_phone!(phone)
      return unless phone
      wanted = phone.gsub(/\D/, "")[-PHONE_MATCH_DIGITS..] || phone.gsub(/\D/, "")
      return if wanted.length < 7

      @text = @text.gsub(PHONE_LIKE) do |match|
        digits = match.gsub(/\D/, "")
        digits.end_with?(wanted) ? TOKEN : match
      end
    end
  end
end
