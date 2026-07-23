{{- define "freshservice-exporter.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "freshservice-exporter.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{- define "freshservice-exporter.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "freshservice-exporter.labels" -}}
helm.sh/chart: {{ include "freshservice-exporter.chart" . }}
{{ include "freshservice-exporter.selectorLabels" . }}
{{- if .Chart.AppVersion }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{- define "freshservice-exporter.selectorLabels" -}}
app.kubernetes.io/name: {{ include "freshservice-exporter.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "freshservice-exporter.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}
{{- default (include "freshservice-exporter.fullname" .) .Values.serviceAccount.name }}
{{- else }}
{{- default "default" .Values.serviceAccount.name }}
{{- end }}
{{- end }}

{{- define "freshservice-exporter.secretName" -}}
{{- if .Values.freshservice.existingSecret }}
{{- .Values.freshservice.existingSecret }}
{{- else }}
{{- include "freshservice-exporter.fullname" . }}
{{- end }}
{{- end }}
