Safer option (no need to open 5000 publicly): SSH tunnel


ssh -i <key.pem> -L 5000:localhost:5000 ec2-user@<EC2_PUBLIC_IP>

# Optional: Allow ec2-user to run Docker without sudo
sudo usermod -aG docker ec2-user