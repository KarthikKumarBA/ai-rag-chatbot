{{- define "northwind.labels" -}}
app.kubernetes.io/part-of: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end }}

{{- define "northwind.wiki.selector" -}}
app.kubernetes.io/name: wiki
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "northwind.rag.selector" -}}
app.kubernetes.io/name: rag
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{- define "northwind.secretName" -}}
{{- required "secrets.existingSecret is required" .Values.secrets.existingSecret -}}
{{- end }}

{{- define "northwind.serviceAccountName" -}}
{{- default (printf "%s-rag" .Release.Name) .Values.serviceAccount.name -}}
{{- end }}
