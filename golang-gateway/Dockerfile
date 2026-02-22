FROM golang:1.21-alpine AS builder

# Install git for go mod download
RUN apk add --no-cache git

WORKDIR /build

# Copy all files including go.mod and source
COPY . .

# Download dependencies and build in one step
RUN go mod tidy && go mod download && CGO_ENABLED=0 GOOS=linux go build -o golang-gateway main.go

# Final stage
FROM alpine:latest

RUN apk --no-cache add ca-certificates

WORKDIR /app

COPY --from=builder /build/golang-gateway .

CMD ["./golang-gateway"]
