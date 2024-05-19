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



sudo snap install helm --classic
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm install nginx-ingress ingress-nginx/ingress-nginx

sudo systemctl enable nginx
sudo systemctl start nginx


eval $(minikube docker-env)
docker build -t cptexcapi:latest .

minikube addons enable ingress
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl apply -f k8s.yaml
kubectl rollout restart deployment cptexcapi-deployment
kubectl rollout restart deployment nginx-ingress-ingress-nginx-controller -n default

MINIKUBE_IP=$(minikube ip)
NGINX_CONF="/etc/nginx/sites-available/default"
sudo cp $NGINX_CONF ${NGINX_CONF}.bak 
NODEPORT=$(kubectl get svc nginx-ingress-ingress-nginx-controller -n default -o jsonpath='{.spec.ports[?(@.port==80)].nodePort}')
PUBLIC_IP=$(curl -s http://checkip.amazonaws.com/)

if grep -Eq "proxy_pass http://[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:3[0-9]{4}" $NGINX_CONF; then
    echo "Updating Nginx configuration with new NodePort..."
    sudo sed -i "s|proxy_pass http://[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+:3[0-9]{4}|proxy_pass http://${MINIKUBE_IP}:${NODEPORT}|g" $NGINX_CONF
else
    if grep -q "server_name ${PUBLIC_IP}.nip.io" $NGINX_CONF; then
        echo "Updating existing server block with new location / configuration..."
        sudo sed -i "/server_name ${PUBLIC_IP}.nip.io;/a \\
\\
    location / {\\
        proxy_pass http://${MINIKUBE_IP}:${NODEPORT};\\
        proxy_http_version 1.1;\\
        proxy_set_header Upgrade \$http_upgrade;\\
        proxy_set_header Connection \"upgrade\";\\
        proxy_set_header Host \$host;\\
        proxy_cache_bypass \$http_upgrade;\\
        proxy_set_header X-Real-IP \$remote_addr;\\
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;\\
        proxy_set_header X-Forwarded-Proto \$scheme;\\
    }" $NGINX_CONF
    else
        echo "Adding Nginx configuration..."
        sudo sed -i "\$a\\
server {\\
    listen 80;\\
    server_name ${PUBLIC_IP}.nip.io;\\
\\
    location / {\\
        proxy_pass http://${MINIKUBE_IP}:${NODEPORT};\\
        proxy_http_version 1.1;\\
        proxy_set_header Upgrade \$http_upgrade;\\
        proxy_set_header Connection \"upgrade\";\\
        proxy_set_header Host \$host;\\
        proxy_cache_bypass \$http_upgrade;\\
        proxy_set_header X-Real-IP \$remote_addr;\\
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;\\
        proxy_set_header X-Forwarded-Proto \$scheme;\\
    }\\
}" $NGINX_CONF
    fi
fi

sudo nginx -t && sudo systemctl reload nginx

sleep 20 # wait for the pods to start
echo "Minikube IP: $MINIKUBE_IP"
echo "Public IP: $PUBLIC_IP"
kubectl get pods
kubectl get hpa
kubectl get svc
kubectl get ingress
kubectl get pods -n kube-system -l k8s-app=metrics-server