#!/usr/bin/env ruby

require "cgi"
require "json"
require "net/http"
require "optparse"

MTEXT_ADAPTER_URL = "http://localhost:8080/"
SOCKET_TIMEOUT = 15.0
POLL_INTERVAL = 5.0
RESPONSE_LIMIT = 1024 * 1024


# Führt einen Request aus und gibt die Antwort als JSON zurück.
def send_request(request)
  http = Net::HTTP.new(request.uri.host, request.uri.port)

  # Die Antwort vollständig lesen, bevor Verbindung und gegebenenfalls Uploaddatei schließen.
  response = http.start { |connection| # Session wird auf- und wieder abgebaut
      connection.request(request)
  }

  return parse_response(response)

rescue Timeout::Error, SocketError, SystemCallError, IOError => error
  raise "Adapteraufruf ist fehlgeschlagen: #{error.message}"
end


# Prüft Größe, HTTP-Status und JSON-Form
def parse_response(response)
  body = response.body.to_s

  # Fehlerantworten als JSON lesen
  document = JSON.parse(body)
  raise "Adapterantwort ist kein JSON-Objekt" unless document.is_a?(Hash)

  unless response.is_a?(Net::HTTPSuccess)
      message = document["meldung"] || body
      raise "Adapter antwortet mit HTTP #{response.code}: #{message}"
  end

  return document

rescue JSON::ParserError => error
  raise "Adapter antwortet nicht mit gültigem JSON: #{error.message}"
end


# Auftrag anlegen, mit dem request_document als JSON im POST-Body
def create(request_document, idempotency_key)
  request = Net::HTTP::Post.new(URI(MTEXT_ADAPTER_URL) + "/sync")
  request["Content-Type"] = "application/json"
  request["Idempotency-Key"] = idempotency_key
  request.body = JSON.generate(request_document)

  send_request(request)
end


# Überträgt ein (angekündigtes) Archiv als Datenstrom zum vorhandenen Auftrag
def upload(auftrag_id, archive_name, archive_path)
  request = Net::HTTP::Put.new(MTEXT_ADAPTER_URL + auftrag_id + "/archive/" + archive_name)
  request["Content-Type"] = "application/gzip"
  request.content_length = File.size(archive_path)

  # Datei nicht puffen sondern direkt senden
  File.open(archive_path, "rb") do |file|
    request.body_stream = file

    return send_request(request)
  end
end


# Aktuellen Status abfragen
def get(auftrag_id)
  send_request(Net::HTTP::Get.new(MTEXT_ADAPTER_URL + auftrag_id))
end


# Auftrag löschen
def delete(auftrag_id)
  document = send_request(Net::HTTP::Delete.new(MTEXT_ADAPTER_URL + auftrag_id))

  if not document["ok"] == true
    raise "Adapter bestätigt das Löschen nicht"
  end

  return document
end



def execute(command)
  case command
  when "create"
    create({'foo':'bar'}, "12345")

  when "upload"
    archive = @options[:file]
    name = File.basename(archive)
    upload(@options[:auftrag_id], name, archive)

  when "get"
    get(@options[:auftrag_id])

  when "delete"
    delete(@options[:auftrag_id])

  else
    raise OptionParser::ParseError, "Unbekannter Befehl: #{command}"
  end
end


# the main function, gets called on the last line of this script
def main
  # parse command line arguments
  @options = {}
  parser = OptionParser.new do |parser|
      parser.banner = "Usage: ruby main.rb <create|upload|status|delete> [Optionen]"
      parser.on("--key KEY", "Idempotency-Key for POST") { |value| @options[:idempotency_key] = value }
      parser.on("--auftrag-id ID", "Auftrag-ID") { |value| @options[:auftrag_id] = value }
      parser.on("--file FILE", "Upload file") { |value| @options[:archive] = value }
  end
  command = ARGV.shift
  parser.parse!(ARGV)
  raise OptionParser::ParseError, parser.to_s if command.nil?

  result = execute(command)

  puts JSON.pretty_generate(result)

  exit 0
end


main
