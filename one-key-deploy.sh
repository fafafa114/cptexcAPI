#!/bin/bash

if ! systemctl is-active --quiet docker; then
    echo "Starting Docker..."
    sudo systemctl start docker
else
    echo "Docker is running"
fi

if ! minikube version > /dev/null 2>&1; then
    echo "Installing Minikube..."
    curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64
    sudo install minikube-linux-amd64 /usr/local/bin/minikube && rm minikube-linux-amd64
else
    echo "Minikube is installed"
fi

if ! minikube status > /dev/null 2>&1; then
    echo "Starting Minikube..."
    minikube start
else
    echo "Minikube is running"
fi

if ! nginx -v > /dev/null 2>&1; then
    echo "Installing Nginx..."
    sudo apt update && sudo apt install nginx -y
else
    echo "Nginx Installed"
fi

PUBLIC_IP=$(curl -s http://checkip.amazonaws.com/)
sudo systemctl start nginx
sudo systemctl enable nginx

MINIKUBE_IP=$(minikube ip)
echo "Minikube IP: $MINIKUBE_IP"
echo "Public IP: $PUBLIC_IP"

NGINX_CONF="/etc/nginx/sites-available/default"
sudo cp $NGINX_CONF ${NGINX_CONF}.bak 

eval $(minikube docker-env)
docker build -t cptexcapi:latest .

kubectl apply -f k8s.yaml
kubectl rollout restart deployment cptexcapi-deployment

if ! grep -q "proxy_pass http://${MINIKUBE_IP}:30000;" $NGINX_CONF; then
    echo "Adding Nginx configuration..."
    sudo sed -i "\$a\
    server {\
        listen 80;\
        server_name ${PUBLIC_IP}.nip.io;\
\
        location / {\
            proxy_pass http://${MINIKUBE_IP}:30000; \
            proxy_http_version 1.1;\
            proxy_set_header Upgrade \$http_upgrade;\
            proxy_set_header Connection \"upgrade\";\
            proxy_set_header Host \$host;\
            proxy_cache_bypass \$http_upgrade;\
            proxy_set_header X-Real-IP \$remote_addr;\
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;\
            proxy_set_header X-Forwarded-Proto \$scheme;\
        }\
    }" $NGINX_CONF
fi

sudo nginx -t && sudo systemctl reload nginx
